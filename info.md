While Home Assistant does provide built-in services for creating backups, these are not particularly user-friendly and do not provide a way to automatically remove them, this custom component aims to fix that.

**Note: Requires the Home Assistant [Supervisor](https://www.home-assistant.io/installation) to Create Backups.**

## Features
* `keep_days` parameter to automatically remove backups.
* `keep_days` can be set individually for each service call.
* Provides Documented Backup Services (Partial, Full backups).
* Support for Generational Backup Schemes.
* Download backups to a specified directory after completion (for example a usb drive).
* Allows use of addon names instead of slugs.
* Allows friendly folder names.
* Adds a sensor to monitor the status of your backups.

## Services
* **auto_backup.backup_full**
* **auto_backup.backup_partial**
* **auto_backup.purge**

For more information and examples check the [full documentation](https://github.com/jcwillox/hass-auto-backup).

## Events
* **auto_backup.backup_start**
* **auto_backup.backup_successful**
* **auto_backup.backup_failed**
* **auto_backup.purged_backups**

## Configuration

Auto Backup can be setup via the UI, go to the Integrations menu and add `Auto Backup`.

On Home Assistant 2021.3.0 and above you can use the badge below to automatically start the setup.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=auto_backup)

### Configuration Variables

- **auto_purge** _(boolean) (Optional)_
  - _Default value:_ `true`
  - This option will automatically purge any expired backups when creating a new backup.

- **backup_timeout** _(integer) (seconds) (Optional)_
  - _Default value:_ `1200` (20 min)
  - You can increase this value if you get timeout errors when creating a backup. This can happen with very large backups.
  
## Images

<img src="https://github.com/jcwillox/hass-auto-backup/blob/master/example-sensor.png?raw=true" width="400px">
