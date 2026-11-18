# Verified NAS backups

This optional feature adds an optional NAS destination to Auto Backup. Existing installations keep their normal behaviour until NAS mode is enabled in integration options. NAS mode requires Home Assistant OS/Supervisor and SMB2/3. Credentials are stored in Home Assistant integration options and are never included in sensor attributes or NAS events. Use a dedicated NAS account restricted to the backup folder.

## Verification contract

1. Create the original Supervisor backup locally.
2. Stream its original bytes into a temporary NAS file while computing SHA-256.
3. Read the entire NAS file back and compare both byte count and SHA-256.
4. Rename the verified file, write and read back a standard .sha256 sidecar, and save an independent receipt in Home Assistant storage.
5. Only then emit auto_backup.backup_successful with nas_verified: true.
6. Apply calendar retention only after verified success. Failed uploads never trigger rotation. An integrity failure suspends rotation until a full verification succeeds.

A matching checksum proves that stored bytes match the reference. It is not a full restore test, signature, encryption, ransomware protection or proof that every application can recover. Export the emergency kit separately if encryption is enabled. NAS snapshots and an independent off-site copy remain useful.

## Configuration

Install or update Auto Backup using its normal installation method, then restart Home Assistant. The NAS functionality is opt-in through integration options.

Open its options and enable verified NAS copies. Supply the NAS address, SMB share, relative folder, username, password and workgroup. The destination folder must already exist; leave the relative folder blank to use the share root. A blank password preserves an existing password.

For a NAS with a network recycle bin, use a dedicated backup share with that bin disabled if retention should immediately reclaim space. SMB deletion normally follows the NAS recycle policy; this integration does not bypass it or empty a shared recycle bin. NAS snapshots and off-site retention can also retain old data independently.

Defaults: 7 daily dates, 4 Sundays, 2 monthly copies (the first available Sunday in each month), and 1 verified local copy. A single archive can satisfy several rules and is never duplicated for this reason. The latest archive for each calendar date wins. Missing historical backups cannot be recreated; coverage grows over time. Names use the Home Assistant timezone.

In NAS mode, do not combine download_path with NAS options. Local keep_days is superseded by verified local-copy retention. Turn auto_purge off to disable both NAS and local rotation. Unrelated manual local backups are preserved. NAS files are limited to this installation's random namespace. Unknown files and directories are never recursively deleted.

## Existing Samba Backup installations

Keep the previous process working until a new full backup has been verified. **Before writing any sidecars, disable the old Samba rotation or set its retention to all.** Some old versions match .tar.sha256 as if it were a backup. Enable legacy management only for a dedicated folder whose Samba_Backup_*.tar archives you intend this integration to manage.

Call auto_backup.verify_nas with adopt_legacy: true once to validate old unencrypted archives, read every compressed member to its CRC, and establish checksum baselines. Where an original local archive survives, its SHA-256 is compared independently. For older copies without an original, this is explicitly a validated-archive baseline, not proof of equality with a lost original. Encrypted legacy archives without a baseline cannot be adopted automatically.

## Monitoring

The NAS backup sensor reports copy counts, latest archive time, checksum state and verification timestamps. auto_backup.check_nas lists archives and dates; it does not read all archive contents. auto_backup.verify_nas rereads every managed file against both the NAS sidecar and independent HA receipts. Schedule it periodically. Call long operations from a script rather than an HTTP request with a short timeout.

Events: auto_backup.backup_failed for backup/copy failure; auto_backup.nas_failed for verification, check or retention failure. No notification destination is hardcoded. Configure your own notifications and missing-backup watchdog. Metadata checks run hourly and consider a backup stale after 26 hours.

## Recovery

Download the desired .tar and .sha256 from the NAS. Verify locally with sha256sum -c ARCHIVE.tar.sha256 (or compare Get-FileHash -Algorithm SHA256 on Windows). Restore the original archive through Home Assistant's supported backup restore workflow. Keep any encryption emergency kit outside this HA installation.

An HA receipt is stored at .storage/auto_backup.nas_verification. Preserve it with the HA configuration: it can detect alteration of both the NAS file and its sidecar. If the entire HA installation is lost, a sidecar alone detects accidental corruption but is not an independent authenticity guarantee.

## Tests

Run python -m unittest discover -s tests -p test_verified_nas.py -v for standalone SMB simulation and calendar-retention tests. Run the upstream suite and manager-flow regressions in a compatible Home Assistant environment.
