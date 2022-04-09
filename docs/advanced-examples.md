# Advanced Examples

## Generational Backups

### Preface

Generational backups [(wiki)](https://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son) allow you to store backups over a long period of time while still having frequent enough backups to be useful for recovery. This is done by reducing the frequency of backups as they get older. <br>

!!! info ""
    Personally I take a backup of the Home Assistant configuration every 3 hours for the first 2 days, then full backups each day for a week, and finally each week for a month.

For example, lets say my database has corrupted and I want to restore it.

If it's been less than 48 hours since it corrupted then I can restore to the exact point before it corrupted +/- 1.5 hours (if you're monitoring trends you don't want to lose hours worth of data, so 1.5 is pretty good),

If 48 hours have passed then I can restore to any point +/- 12 hours over the past 5 days (minus the two where the db was corrupted).

Over a week I can restore to any point +/- 1 week over the past 3 weeks, while +/- 1 week isn't very useful for restoring a database, it can be useful for subtle thing you don't notice, like if you accidentally deleted something.

This is substantially more efficient than storing a backup every 3 hours for a month, and while you lose some accuracy as the backups get older, most failures (if they even occur) will be noticed within 48 hours,

Also, most things other than your database don't change that often so a 4-week-old backup of your home assistant config may be the same as 1 day old backup.
Also in my case the 3 hourly backup only backs up the important files to save on storage, whereas my daily/weekly backups are full backups.

Of course, you can tweak these values to your liking, or even add a month/yearly backup schedule 👍.

### Automations

```yaml
automation:
  - alias: "AutoBackup: Hourly Backup"
    trigger:
      platform: time_pattern # Perform backup every 3 hours.
      hours: "/3"
    action:
      service: auto_backup.backup_partial # Only perform a partial backup to save storage.
      data:
        name: "AutoBackup: {{ now().strftime('%a, %-I:%M %p (%d/%m/%Y)') }}"
        addons:
          - core_mariadb # It doesn't matter if you use the addon slug or name. Name is easier.
          - core_mosquitto
        folders:
          - homeassistant
          - share
          - ssl
        keep_days: 2

  - alias: "AutoBackup: Daily Backup"
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
      service: auto_backup.backup_full
      data:
        name: "DailyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
        keep_days: 7

  - alias: "AutoBackup: Weekly Backup"
    trigger:
      platform: time
      at: "02:30:00"
    condition:
      condition: time # On Mondays perform a weekly backup
      weekday:
        - mon
    action:
      service: auto_backup.backup_full
      data:
        name: "WeeklyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
        keep_days: 28 # Store backup for a month, basically perform 1 backup each week and store for 4 weeks.
```
