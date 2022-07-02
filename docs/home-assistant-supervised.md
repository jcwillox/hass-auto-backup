# Home Assistant Supervised

## Limitations

### Stability (Timeouts)

When using Home Assistant Supervised, Auto Backup must make a request to the Supervisor to create a backup and has to keep that request open until the backup completes, at which point the backups unique id (slug) is returned. This can create stability issues when backups take a long time to create, e.g. 20 minutes+, as the request may fail and Auto Backup will not know the id of the backup to monitor for completion or deletion. In this case, the backup will still be created.

By default, Auto Backup will assume a backup failed if it takes longer than 20 minutes. You can increase this limit using the "Backup Timeout" option, but you may run into reliability issues.

### Include / Exclude

The scope of the `include` and `exclude` options are limited by what Home Assistant allows, you can only include or exclude addons and the base folders like `config`, `share`, `media`, but not subdirectories of them.
