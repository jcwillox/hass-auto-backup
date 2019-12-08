While Home Assistant does provide built-in services for creating backups, these are not documented and do not provide a way to automatically remove them, this custom component aims to fix that.

**Note: Requires [Hass.io](https://www.home-assistant.io/hassio) to Create Snapshots.**

## Features
* `keep_days` parameter to automatically remove backups.
* `keep_days` can be set individually for each service call.
* Provides Documented Backup Services (Partial, Full snapshots).
* Support for Generational Backup Schemes.
* Allows use of addon names instead of slugs.
* Allows friendly folder names.

## Services
* **auto_backup.snapshot_full**
* **auto_backup.snapshot_partial**
* **auto_backup.purge**

For more information and examples check the [full documentation](https://github.com/jcwillox/ha-auto-backup).

## Configuration

Just add `auto_backup` to your home assistant configuration.yaml file.

```yaml
# Example configuration.yaml entry
auto_backup:
  auto_purge: true
```

### Configuration Variables

- **auto_purge** _(boolean) (Optional)_
  - _Default value:_ `true`
  - This option will automatically purge any expired snapshots when creating a new snapshot.