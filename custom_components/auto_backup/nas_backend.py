"""Blocking SMB operations. Call only in an executor; never log credentials."""

from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import io
import posixpath
import re
import socket
import tarfile
import tempfile

from .nas_policy import CURRENT, LEGACY, make_plan, parse_archive


class NasError(RuntimeError):
    """A safely reportable NAS failure."""


class ChecksumMismatch(NasError):
    """The stored file does not match its independent reference."""


def validate_config(config):
    for key in ("server", "share"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise NasError("NAS server and share are required")
    if any(c in config["server"] for c in "/\\\r\n") or any(
        c in config["share"] for c in "/\\\r\n*?"
    ):
        raise NasError("Invalid NAS server or share")
    folder = config.get("folder", "").replace("\\", "/")
    if (
        folder.startswith("/")
        or any(p in (".", "..") for p in folder.split("/"))
        or any(c in folder for c in "*?\r\n")
    ):
        raise NasError(
            "NAS folder must be a relative path without traversal or wildcards"
        )
    if config.get("username") and not config.get("password"):
        raise NasError("NAS password is required")
    for name, limit in (
        ("daily", 90),
        ("weekly", 52),
        ("monthly", 24),
        ("keep_local", 20),
    ):
        if not isinstance(config.get(name), int) or not 1 <= config[name] <= limit:
            raise NasError("Invalid NAS retention count")


def _path(config, name):
    if not name or name in (".", "..") or any(c in name for c in "/\\*?\r\n"):
        raise NasError("Invalid archive filename")
    return posixpath.join(config.get("folder", ""), name)


@contextmanager
def connection(config, factory=None):
    validate_config(config)
    if factory is None:
        from smb.SMBConnection import SMBConnection

        factory = SMBConnection
    conn = factory(
        config.get("username", ""),
        config.get("password", ""),
        "HAAUTOBACKUP",
        "NAS",
        domain=config.get("workgroup", "WORKGROUP"),
        use_ntlm_v2=True,
        sign_options=1,
        is_direct_tcp=True,
    )
    try:
        if not conn.connect(
            config["server"], 445, sock_family=socket.AF_INET, timeout=15
        ):
            raise NasError("NAS authentication failed")
        if not conn.isUsingSMB2:
            raise NasError("Legacy SMB1 is not supported")
        yield conn
    except NasError:
        raise
    except Exception as error:
        raise NasError("NAS operation failed (" + type(error).__name__ + ")") from None
    finally:
        conn.close()


class DigestWriter:
    def __init__(self, target=None):
        self.digest = hashlib.sha256()
        self.count = 0
        self.target = target

    def write(self, data):
        self.digest.update(data)
        self.count += len(data)
        if self.target is not None:
            self.target.write(data)
        return len(data)


class DigestReader:
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()
        self.count = 0

    def read(self, size=-1):
        data = self.source.read(size)
        self.digest.update(data)
        self.count += len(data)
        return data


def _read_hash(conn, config, name, target=None):
    writer = DigestWriter(target)
    conn.retrieveFile(config["share"], _path(config, name), writer, timeout=900)
    return writer.digest.hexdigest(), writer.count


def _write_sidecar(conn, config, name, digest):
    content = (digest + "  " + name + "\n").encode()
    partial, final = name + ".sha256.partial", name + ".sha256"
    conn.storeFile(
        config["share"], _path(config, partial), io.BytesIO(content), timeout=30
    )
    conn.rename(
        config["share"], _path(config, partial), _path(config, final), timeout=30
    )
    check = io.BytesIO()
    conn.retrieveFile(config["share"], _path(config, final), check, timeout=30)
    if check.getvalue() != content:
        raise ChecksumMismatch("Checksum sidecar read-back failed")


def _sidecar_hash(conn, config, name):
    value = io.BytesIO()
    conn.retrieveFile(
        config["share"], _path(config, name + ".sha256"), value, timeout=30
    )
    text = value.getvalue().decode("ascii").strip()
    match = re.fullmatch(r"([a-f0-9]{64})  " + re.escape(name), text)
    if not match:
        raise NasError("Invalid checksum sidecar")
    return match.group(1)


def _entries(conn, config, namespace):
    if not re.fullmatch(r"[a-f0-9]{12}", namespace):
        raise NasError("Invalid backup namespace")
    entries = conn.listPath(
        config["share"], config.get("folder", "") or "/", timeout=30
    )
    archives = []
    for entry in entries:
        if entry.isDirectory:
            continue
        own = entry.filename.startswith("AutoBackup_" + namespace + "_")
        legacy = config.get("manage_legacy", False) and LEGACY.fullmatch(entry.filename)
        if (
            own and CURRENT.fullmatch(entry.filename) or legacy
        ) and entry.file_size <= 0:
            raise ChecksumMismatch("An owned backup is empty")
        if (own or legacy) and (
            item := parse_archive(
                entry.filename, entry.file_size, entry.last_write_time
            )
        ):
            archives.append(item)
    return archives, {entry.filename for entry in entries if not entry.isDirectory}


def _plan(conn, config, namespace, now):
    archives, names = _entries(conn, config, namespace)
    if not archives:
        return archives, names, None
    return (
        archives,
        names,
        make_plan(
            archives, now.date(), config["daily"], config["weekly"], config["monthly"]
        ),
    )


def scan(config, namespace, now, factory=None):
    with connection(config, factory) as conn:
        archives, names, plan = _plan(conn, config, namespace, now)
        if not plan:
            return {
                "status": "empty",
                "copies": 0,
                "daily": 0,
                "weekly": 0,
                "monthly": 0,
                "missing_checksums": 0,
            }
        latest = datetime.fromisoformat(plan["latest_timestamp"]).replace(
            tzinfo=now.tzinfo
        )
        age = (now - latest).total_seconds() / 3600
        if age < 0:
            raise NasError("Backup timestamp is in the future")
        return {
            "status": "ok" if age <= 26 else "stale",
            "copies": len(archives),
            "daily": len(plan["daily"]),
            "weekly": len(plan["weekly"]),
            "monthly": len(plan["monthly"]),
            "last_backup": latest.isoformat(),
            "age_hours": round(age, 2),
            "missing_checksums": sum(a.name + ".sha256" not in names for a in archives),
            "plan": plan,
        }


def transfer(config, namespace, slug, when, source_factory, factory=None):
    if not re.fullmatch(r"[a-f0-9]{8}", slug) or not re.fullmatch(
        r"[a-f0-9]{12}", namespace
    ):
        raise NasError("Invalid backup identifier")
    name = (
        "AutoBackup_"
        + namespace
        + "_"
        + when.strftime("%Y_%m_%d_%H_%M_%S")
        + "_"
        + slug
        + ".tar"
    )
    partial = "." + name + ".partial"
    with connection(config, factory) as conn:
        _, names = _entries(conn, config, namespace)
        if name in names or partial in names:
            raise NasError("Backup destination already exists; preserved")
        committed = False
        try:
            with source_factory() as response:
                if getattr(response, "status", 200) != 200:
                    raise NasError("Backup download failed")
                headers = getattr(response, "headers", {})
                expected = int(headers.get("Content-Length", 0))
                reader = DigestReader(response)
                conn.storeFile(
                    config["share"], _path(config, partial), reader, timeout=900
                )
                source_digest, size = reader.digest.hexdigest(), reader.count
                if not size or (expected and expected != size):
                    raise NasError("Backup source was truncated")
            nas_digest, nas_size = _read_hash(conn, config, partial)
            if source_digest != nas_digest or size != nas_size:
                raise ChecksumMismatch(
                    "NAS SHA-256 does not match the original; old backups preserved"
                )
            conn.rename(
                config["share"], _path(config, partial), _path(config, name), timeout=30
            )
            committed = True
            _write_sidecar(conn, config, name, source_digest)
            attrs = conn.getAttributes(config["share"], _path(config, name), timeout=30)
            return {
                "slug": slug,
                "name": name,
                "sha256": source_digest,
                "bytes": size,
                "modified": attrs.last_write_time,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "verification": "source_and_nas_sha256",
                "local_removed": False,
            }
        finally:
            if not committed:
                try:
                    conn.deleteFiles(
                        config["share"], _path(config, partial), timeout=15
                    )
                except Exception:
                    pass


def purge(config, namespace, receipts, now, factory=None):
    with connection(config, factory) as conn:
        archives, names, plan = _plan(conn, config, namespace, now)
        if not plan:
            raise NasError("No backup: deletion forbidden")
        latest = datetime.fromisoformat(plan["latest_timestamp"]).replace(
            tzinfo=now.tzinfo
        )
        if not 0 <= (now - latest).total_seconds() <= 26 * 3600:
            raise NasError("Backup is stale or future-dated: deletion forbidden")
        receipt = receipts.get(plan["latest"])
        if not receipt:
            raise NasError(
                "Latest backup has no verified reference: deletion forbidden"
            )
        latest_item = next(a for a in archives if a.name == plan["latest"])
        if receipt["bytes"] != latest_item.size:
            raise ChecksumMismatch("Latest backup size changed")
        if _sidecar_hash(conn, config, plan["latest"]) != receipt["sha256"]:
            raise ChecksumMismatch("Latest checksum reference changed")
        verified = datetime.fromisoformat(receipt["verified_at"])
        if (now - verified).total_seconds() > 900 or receipt.get(
            "modified"
        ) != latest_item.modified:
            digest, size = _read_hash(conn, config, plan["latest"])
            if digest != receipt["sha256"] or size != receipt["bytes"]:
                raise ChecksumMismatch(
                    "Latest backup no longer matches: deletion forbidden"
                )
        by_name = {a.name: a for a in archives}
        for name in plan["delete"]:
            attrs = conn.getAttributes(config["share"], _path(config, name), timeout=30)
            if (
                attrs.isDirectory
                or attrs.file_size != by_name[name].size
                or attrs.last_write_time != by_name[name].modified
            ):
                raise NasError("Backup changed: deletion cancelled")
        removed = []
        for name in plan["delete"]:
            conn.deleteFiles(
                config["share"],
                _path(config, name),
                delete_matching_folders=False,
                timeout=30,
            )
            removed.append(name)
            if name + ".sha256" in names:
                conn.deleteFiles(
                    config["share"],
                    _path(config, name + ".sha256"),
                    delete_matching_folders=False,
                    timeout=30,
                )
        remaining, _ = _entries(conn, config, namespace)
        if {a.name for a in remaining} != {a.name for a in archives} - set(removed):
            raise NasError("Retention post-check failed")
        return {
            "removed": removed,
            "remaining": [a.name for a in remaining],
            "plan": plan,
        }


def _validate_plain_archive(file):
    file.seek(0)
    with tarfile.open(fileobj=file, mode="r:") as archive:
        members = {
            m.name.removeprefix("./"): m for m in archive.getmembers() if m.isfile()
        }
        if (
            not ("backup.json" in members or "snapshot.json" in members)
            or "homeassistant.tar.gz" not in members
        ):
            raise NasError("Legacy archive is not a complete HA backup")
        for name, member in members.items():
            if name.endswith(".tar.gz"):
                with gzip.GzipFile(fileobj=archive.extractfile(member)) as content:
                    while content.read(8 * 1024 * 1024):
                        pass


def verify(config, namespace, receipts, now, adopt_legacy=False, factory=None):
    with connection(config, factory) as conn:
        archives, names, plan = _plan(conn, config, namespace, now)
        if not archives:
            raise NasError("No NAS backups found")
        checked, adopted, updates, missing = [], [], {}, []
        for item in archives:
            reference = receipts.get(item.name)
            if item.name + ".sha256" in names:
                expected = _sidecar_hash(conn, config, item.name)
                if reference and reference["sha256"] != expected:
                    raise ChecksumMismatch("Stored reference was modified")
                digest, size = _read_hash(conn, config, item.name)
                if digest != expected or size != item.size:
                    raise ChecksumMismatch("NAS archive failed its SHA-256 check")
            elif adopt_legacy and LEGACY.fullmatch(item.name):
                with tempfile.TemporaryFile() as temporary:
                    digest, size = _read_hash(conn, config, item.name, temporary)
                    if size != item.size:
                        raise ChecksumMismatch("Legacy archive size changed")
                    _validate_plain_archive(temporary)
                _write_sidecar(conn, config, item.name, digest)
                adopted.append(item.name)
            else:
                missing.append(item.name)
                continue
            checked.append(item.name)
            updates[item.name] = {
                **(reference or {}),
                "name": item.name,
                "sha256": digest,
                "bytes": size,
                "modified": item.modified,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "created_at": (reference or {}).get(
                    "created_at", item.timestamp.replace(tzinfo=now.tzinfo).isoformat()
                ),
                "verification": (reference or {}).get(
                    "verification",
                    (
                        "validated_archive_baseline"
                        if item.name in adopted
                        else "nas_sidecar_sha256"
                    ),
                ),
            }
        return {
            "checked": checked,
            "adopted": adopted,
            "missing": missing,
            "receipts": updates,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }


def source_digest(source_factory):
    """Hash a surviving local original when adopting an existing NAS backup."""
    with source_factory() as response:
        if getattr(response, "status", 200) != 200:
            raise NasError("Local backup read failed")
        reader = DigestReader(response)
        while reader.read(8 * 1024 * 1024):
            pass
        expected = int(getattr(response, "headers", {}).get("Content-Length", 0))
        if not reader.count or (expected and expected != reader.count):
            raise NasError("Local backup was truncated")
        return reader.digest.hexdigest(), reader.count
