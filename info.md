Auto Backup is an Improved Backup Service for Home Assistant that can Automatically Remove Backups and Supports Generational Backup Schemes.

> While Home Assistant does provide built-in services for creating backups, they do not provide the ability to exclude items from a backup, or a way to automatically remove them, this custom component aims to fix that.

For more information and examples check the [documentation](https://jcwillox.github.io/hass-auto-backup).

## Features
* Provides more advanced and configurable [service calls](https://jcwillox.github.io/hass-auto-backup/services).
* [Exclude addons/folders](https://jcwillox.github.io/hass-auto-backup/services) from a backup.
* [Automatically delete backups](https://jcwillox.github.io/hass-auto-backup/services/#keep-days) after an individually specified amount of time.
* [Download backups](https://jcwillox.github.io/hass-auto-backup/services/#download-path) to a specified directory after completion (for example a usb drive).
* Allows the use of [addon names instead of slugs](https://jcwillox.github.io/hass-auto-backup/services/#addon-and-folder-names).
* Provides a [sensor](https://jcwillox.github.io/hass-auto-backup/sensors) to monitor the status of your backups.
* Creates [events](https://jcwillox.github.io/hass-auto-backup/events) for when backups are started/created/failed/deleted.
* Supports [generational backup](https://jcwillox.github.io/hass-auto-backup/advanced-examples/#generational-backups) schemes.

## Services

[Automation Examples using Services](https://jcwillox.github.io/hass-auto-backup/examples)

* [`auto_backup.backup`](https://jcwillox.github.io/hass-auto-backup/services/#auto_backupbackup)
* [`auto_backup.backup_full`](https://jcwillox.github.io/hass-auto-backup/services/#auto_backupbackup_full)
* [`auto_backup.backup_partial`](https://jcwillox.github.io/hass-auto-backup/services/#auto_backupbackup_partial)
* [`auto_backup.purge`](https://jcwillox.github.io/hass-auto-backup/services/#auto_backupbackup_purge)

## Events

[Automation Example using Events](https://jcwillox.github.io/hass-auto-backup/events/#example-automation-using-events)

* [`auto_backup.backup_start`](https://jcwillox.github.io/hass-auto-backup/events)
* [`auto_backup.backup_successful`](https://jcwillox.github.io/hass-auto-backup/events)
* [`auto_backup.backup_failed`](https://jcwillox.github.io/hass-auto-backup/events)
* [`auto_backup.purged_backups`](https://jcwillox.github.io/hass-auto-backup/events)

## Configuration

After installing Auto Backup via [HACS](https://hacs.xyz/), it can then be setup via the UI, by going to **Configuration** → **Devices & Services** → **Add Integration** → **Auto Backup** or by clicking the button below.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=auto_backup)

### Options

- **Automatically delete expired backups**
  - This option will automatically purge any expired backups when creating a new backup.

- **Backup Timeout**
  - You can increase this value if you get timeout errors when creating a backup. This can happen with very large backups. Increasing this might make Auto Backup less reliable at monitoring backups to delete.

## Images

<img alt="Sensor Example" src="https://github.com/jcwillox/hass-auto-backup/blob/main/docs/assets/example-sensor.png?raw=true" width="400px">

---

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/jcwillox)
