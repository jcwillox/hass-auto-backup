# <span style="font-family: 'Segoe UI Emoji'">🗃</span> Auto Backup

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

Improved Backup Service for [Hass.io](https://www.home-assistant.io/hassio) that can Automatically Remove Snapshots and Supports Generational Backup Schemes.

While Home Assistant does provide built-in services for creating backups these are not documented and do not provide a way to automatically remove them, this custom component aims to fix that.

## Services

### auto_backup.snapshot_full

| Parameter   | Description                            | Requirement  | Type     | Example                                           |
| ----------- | -------------------------------------- | ------------ | -------- | ------------------------------------------------- |
| `name`      | Backup name.                           | **Optional** | `string` | Automatic Backup {{ now().strftime('%Y-%m-%d') }} |
| `password`  | Optional password to secure backup.    | **Optional** | `string` | 1234                                              |
| `keep_days` | The number of days to keep the backup. | **Optional** | `float`  | 2                                                 |
|             |                                        |              |          | `keep_days` can be a float like 0.5, for 12 hours |

---

### auto_backup.snapshot_partial

| Parameter   | Description                            | Requirement  | Type     | Example                                           |
| ----------- | -------------------------------------- | ------------ | -------- | ------------------------------------------------- |
| `name`      | Backup name.                           | **Optional** | `string` | Automatic Backup {{ now().strftime('%Y-%m-%d') }} |
| `addons`    | List of addons to backup.              | **Optional** | `list`   | [ "core_mariadb", "core_mosquitto" ]              |
| `folders`   | List of folders to backup.             | **Optional** | `list`   | [ "homeassistant", "share", "ssl" ]               |
| `password`  | Optional password to secure backup.    | **Optional** | `string` | 1234                                              |
| `keep_days` | The number of days to keep the backup. | **Optional** | `float`  | 2                                                 |
|             |                                        |              |          | `keep_days` can be a float like 0.5, for 12 hours |

---

### auto_backup.purge

There are no parameters here, just call the service and it will remove any expired snapshots.

This service is useful if you want to manually specify when to purge snapshots,
such as doing a batch delete at 12AM (_Note: expired snapshots are automatically purged when creating new snapshots,
this can be disabled in the [config](#configuration)_.

## Example: Automatic Backups

Perform a partial backup of the home assistant config folder, mariadb and mosquitto every 3 hours,
and store each backup for 2 days.

> ```yaml
> - alias: Perform Auto Backup
>   trigger:
>     - platform: time_pattern
>       hours: "/3"
>   action:
>     - service: auto_backup.snapshot_partial
>       data_template:
>         name: "AutoBackup: {{ now().strftime('%a, %-I:%M %p (%d/%m/%Y)') }}"
>         addons:
>           - core_mariadb
>           - core_mosquitto
>         folders:
>           - homeassistant
>           - share
>           - ssl
>         keep_days: 2
> ```

## Configuration

Just add `auto_backup` to your home assistant configuration.yaml file.

> ```yaml
> # Example configuration.yaml entry
> auto_backup:
>   auto_purge: true
> ```

### Configuration Variables

- **auto_purge** _(boolean) (Optional)_
  - _Default value:_ `true`
  - This option will automatically purge any expired snapshots when creating a new snapshot.

## Advanced Example: Generational Backups
### Preface
Generational backups [(wiki)](https://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son) allow you to store backups over a long period of time while still having frequent enough backups to be useful for recovery. This is done by reducing the frequency of backups as they get older. <br>
_Personally I take a snapshot of home assistant every 3 hours for the first 2 days, then each day for a week, and finally each week for a month._

For example, lets say my database has corrupted and I want to restore it.

If its been less than 48 hours since it corrupted then I can restore to the exact point before it corrupted +/- 1.5 hours (if you're monitoring trends you don't want to lose hours worth of data, so 1.5 is pretty good),

If 48 hours have passed then I can restore to any point +/- 12 hours over the past 5 days (minus the two where the db was corrupted).

Over a week I can restore to any point +/- 1 week over the past 3 weeks, while +/- 1 week isn't very useful for restoring a database, it can be useful for subtle thing you don't notice, like if you accidentally deleted something.

This is substantially more efficient than storing a backup every 3 hours for a month, and while you lose some accuracy as the backups get older, most failures (if they even occur) will be noticed within 48 hours,

Also most things other than your database don't change that often so a 4 week old backup of your home assistant config may be the same as 1 day old backup.
Also in my case the 3 hourly backup only backs up the important files to save on storage, whereas my daily/weekly backups are full snapshots.

Of course you can tweak these values to you liking, or even add a month/yearly backup schedule 👍.
### Automation
```yaml
automation:
  - alias: Perform Auto Backup
    trigger:
      platform: time_pattern # Perform backup every 3 hours.
      hours: "/3"
    action:
      service: auto_backup.snapshot_partial # Only perform a partial snapshot to save storage.
      data_template:
        name: "AutoBackup: {{ now().strftime('%a, %-I:%M %p (%d/%m/%Y)') }}"
        addons:
          - core_mariadb
          - core_mosquitto
        folders:
          - homeassistant
          - share
          - ssl
        keep_days: 2

  - alias: Perform Daily Backup
    trigger:
      platform: time
      at: "02:30:00"
    condition:
      condition: time # Perform backup every day except Mondays.
      weekday:
        - tue
        - wed
        - thu
        - fri
        - sat
        - sun
    action:
      service: auto_backup.snapshot_full
      data_template:
        name: "DailyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
        keep_days: 7

  - alias: Perform Weekly Backup
    trigger:
      platform: time
      at: "02:30:00"
    condition:
      condition: time # On Mondays perform a weekly backup
      weekday:
        - mon
    action:
      service: auto_backup.snapshot_full
      data_template:
        name: "WeeklyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
        keep_days: 28 # Store backup for a month, basically perform 1 backup each week and store for 4 weeks.
```

## Planned Features

- Support for excluding addons/folders from full snapshots.
- Home Assistant config flow support.
