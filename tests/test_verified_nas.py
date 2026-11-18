"""Standalone tests: python -m unittest discover -s tests -p test_verified_nas.py."""

import hashlib
import importlib
import io
from pathlib import Path
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

# Load the independent backend without importing Home Assistant's integration.
PACKAGE = "verified_nas_test_package"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).parents[1] / "custom_components/auto_backup")]
sys.modules[PACKAGE] = package
backend = importlib.import_module(PACKAGE + ".nas_backend")
policy = importlib.import_module(PACKAGE + ".nas_policy")
NS = "abcdef123456"
NOW = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
CONFIG = dict(
    server="nas.invalid",
    share="backups",
    folder="ha",
    username="user",
    password="test-only",
    daily=7,
    weekly=4,
    monthly=2,
    keep_local=1,
    manage_legacy=False,
)


class Response(io.BytesIO):
    def __init__(self, data=b"original backup", status=200, length=None):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Length": str(len(data) if length is None else length)}


class SMB:
    isUsingSMB2 = True

    def __init__(self):
        self.files = {}
        self.modified = {}
        self.deleted = []
        self.corrupt_read = False
        self.change_candidate = None

    def connect(self, *args, **kwargs):
        return True

    def close(self):
        pass

    def put(self, path, data):
        self.files[path] = data
        self.modified[path] = 123.0

    def storeFile(self, share, path, reader, **kwargs):
        self.put(path, b"".join(iter(lambda: reader.read(7), b"")))

    def retrieveFile(self, share, path, writer, **kwargs):
        data = self.files[path]
        if self.corrupt_read and not path.endswith(".sha256"):
            data += b"corruption"
        writer.write(data)

    def rename(self, share, source, target, **kwargs):
        if target in self.files:
            raise RuntimeError("destination exists")
        self.put(target, self.files.pop(source))
        self.modified.pop(source, None)

    def listPath(self, share, folder, **kwargs):
        return [
            SimpleNamespace(
                filename=p.split("/")[-1],
                file_size=len(d),
                last_write_time=self.modified[p],
                isDirectory=False,
            )
            for p, d in self.files.items()
            if p.rsplit("/", 1)[0] == folder
        ]

    def getAttributes(self, share, path, **kwargs):
        if path == self.change_candidate:
            self.modified[path] += 1
        return SimpleNamespace(
            file_size=len(self.files[path]),
            last_write_time=self.modified[path],
            isDirectory=False,
        )

    def deleteFiles(self, share, path, **kwargs):
        self.deleted.append(path)
        del self.files[path]
        self.modified.pop(path, None)


class VerifiedNAS(unittest.TestCase):
    def setUp(self):
        self.smb = SMB()
        self.factory = lambda *a, **kw: self.smb

    def upload(self, **kwargs):
        return backend.transfer(
            CONFIG, NS, "01234567", NOW, lambda: Response(**kwargs), self.factory
        )

    def seed(self, days=90):
        for offset in range(days):
            name = (
                "AutoBackup_"
                + NS
                + "_"
                + (NOW - timedelta(days=offset)).strftime("%Y_%m_%d_%H_%M_%S")
                + "_01234567.tar"
            )
            self.smb.put("ha/" + name, b"backup")
        name = next(iter(self.smb.files)).split("/")[-1]
        digest = hashlib.sha256(b"backup").hexdigest()
        self.smb.put("ha/" + name + ".sha256", (digest + "  " + name + "\n").encode())
        return {
            name: dict(
                name=name,
                bytes=6,
                sha256=digest,
                modified=123.0,
                verified_at=NOW.isoformat(),
            )
        }

    def test_upload_reads_back_and_publishes_sidecar(self):
        receipt = self.upload()
        self.assertEqual(
            receipt["sha256"], hashlib.sha256(b"original backup").hexdigest()
        )
        self.assertIn("ha/" + receipt["name"] + ".sha256", self.smb.files)
        self.assertFalse(any(p.endswith(".partial") for p in self.smb.files))

    def test_corrupt_readback_preserves_old_copy(self):
        self.smb.put("ha/manual.tar", b"old")
        self.smb.corrupt_read = True
        with self.assertRaises(backend.ChecksumMismatch):
            self.upload()
        self.assertEqual(self.smb.files, {"ha/manual.tar": b"old"})

    def test_truncated_source_rejected(self):
        with self.assertRaises(backend.NasError):
            self.upload(length=1000)
        self.assertFalse(self.smb.files)

    def test_http_failure_rejected(self):
        with self.assertRaises(backend.NasError):
            self.upload(status=400)

    def test_empty_source_rejected(self):
        with self.assertRaises(backend.NasError):
            self.upload(data=b"")

    def test_existing_destination_preserved(self):
        self.upload()
        before = dict(self.smb.files)
        with self.assertRaises(backend.NasError):
            self.upload()
        self.assertEqual(before, self.smb.files)

    def test_smb1_rejected(self):
        self.smb.isUsingSMB2 = False
        with self.assertRaises(backend.NasError):
            self.upload()

    def test_traversal_and_wildcards_rejected(self):
        for folder in ("../ha", "/absolute", "ha/*", "ha/../backup", "ha\\..\\backup"):
            with self.subTest(folder=folder), self.assertRaises(backend.NasError):
                backend.validate_config({**CONFIG, "folder": folder})

    def test_retention_union_no_sunday_duplicates(self):
        self.seed()
        archives, _ = backend._entries(self.smb, CONFIG, NS)
        plan = policy.make_plan(archives, NOW.date())
        self.assertEqual(
            [len(plan[k]) for k in ("daily", "weekly", "monthly")], [7, 4, 2]
        )
        self.assertEqual(len(plan["keep"]), len(set(plan["keep"])))
        self.assertTrue(any(len(roles) > 1 for roles in plan["roles"].values()))

    def test_retention_never_touches_unknown_or_other_instance(self):
        receipts = self.seed()
        self.smb.put("ha/manual.tar", b"manual")
        foreign = "ha/AutoBackup_111111111111_2026_01_01_12_00_00_01234567.tar"
        self.smb.put(foreign, b"foreign")
        backend.purge(CONFIG, NS, receipts, NOW, self.factory)
        self.assertIn("ha/manual.tar", self.smb.files)
        self.assertIn(foreign, self.smb.files)

    def test_missing_receipt_prevents_all_deletions(self):
        self.seed()
        with self.assertRaises(backend.NasError):
            backend.purge(CONFIG, NS, {}, NOW, self.factory)
        self.assertFalse(self.smb.deleted)

    def test_stale_backup_prevents_all_deletions(self):
        receipts = self.seed()
        with self.assertRaises(backend.NasError):
            backend.purge(CONFIG, NS, receipts, NOW + timedelta(days=2), self.factory)
        self.assertFalse(self.smb.deleted)

    def test_future_backup_prevents_all_deletions(self):
        receipts = self.seed()
        with self.assertRaises((backend.NasError, ValueError)):
            backend.purge(CONFIG, NS, receipts, NOW - timedelta(hours=1), self.factory)
        self.assertFalse(self.smb.deleted)

    def test_changed_candidate_aborts_before_any_deletion(self):
        receipts = self.seed()
        self.smb.change_candidate = "ha/" + next(iter(receipts)).replace(
            "2026_11_18", "2026_08_21"
        )
        # Pick an actual candidate from the oldest date.
        self.smb.change_candidate = list(self.smb.files)[-2]
        with self.assertRaises(backend.NasError):
            backend.purge(CONFIG, NS, receipts, NOW, self.factory)
        self.assertFalse(self.smb.deleted)

    def test_sidecar_tamper_prevents_deletion(self):
        receipts = self.seed()
        name = next(iter(receipts))
        self.smb.files["ha/" + name + ".sha256"] = (
            "0" * 64 + "  " + name + "\n"
        ).encode()
        with self.assertRaises(backend.ChecksumMismatch):
            backend.purge(CONFIG, NS, receipts, NOW, self.factory)
        self.assertFalse(self.smb.deleted)

    def test_full_verification_detects_archive_and_sidecar_tamper(self):
        receipt = self.upload()
        name = receipt["name"]
        self.smb.put("ha/" + name, b"changed archive")
        digest = hashlib.sha256(b"changed archive").hexdigest()
        self.smb.put("ha/" + name + ".sha256", (digest + "  " + name + "\n").encode())
        with self.assertRaises(backend.ChecksumMismatch):
            backend.verify(CONFIG, NS, {name: receipt}, NOW, factory=self.factory)

    def test_full_verification_success(self):
        receipt = self.upload()
        result = backend.verify(
            CONFIG, NS, {receipt["name"]: receipt}, NOW, factory=self.factory
        )
        self.assertEqual(result["checked"], [receipt["name"]])

    def test_new_verified_copy_replaces_same_calendar_day_without_duplicates(self):
        first = self.upload()
        later = NOW + timedelta(minutes=1)
        second = backend.transfer(
            CONFIG, NS, "76543210", later, lambda: Response(), self.factory
        )
        result = backend.purge(
            CONFIG, NS, {r["name"]: r for r in (first, second)}, later, self.factory
        )
        self.assertEqual(result["remaining"], [second["name"]])
        self.assertNotIn("ha/" + first["name"] + ".sha256", self.smb.files)
        self.assertIn("ha/" + second["name"] + ".sha256", self.smb.files)

    def test_legacy_ignored_unless_explicitly_enabled(self):
        self.smb.put("ha/Samba_Backup_2026_11_18_09_53.tar", b"archive")
        self.assertEqual(backend.scan(CONFIG, NS, NOW, self.factory)["copies"], 0)
        self.assertEqual(
            backend.scan({**CONFIG, "manage_legacy": True}, NS, NOW, self.factory)[
                "copies"
            ],
            1,
        )

    def test_invalid_legacy_archive_not_adopted(self):
        self.smb.put("ha/Samba_Backup_2026_11_18_09_53.tar", b"not an archive")
        with self.assertRaises(backend.NasError):
            backend.verify(
                {**CONFIG, "manage_legacy": True}, NS, {}, NOW, True, self.factory
            )
        self.assertFalse(any(p.endswith(".sha256") for p in self.smb.files))

    def test_empty_owned_archive_is_error(self):
        name = "ha/AutoBackup_" + NS + "_2026_11_18_12_00_00_01234567.tar"
        self.smb.put(name, b"")
        with self.assertRaises(backend.ChecksumMismatch):
            backend.scan(CONFIG, NS, NOW, self.factory)


if __name__ == "__main__":
    unittest.main()
