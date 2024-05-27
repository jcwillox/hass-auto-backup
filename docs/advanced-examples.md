# Advanced Examples

## Generational Backups

???+ blueprint "Blueprint"
    Create backups each day and keep them for a configurable amount of time, backups are stored less frequently the older they are.

    [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A//raw.githubusercontent.com/jcwillox/home-assistant-blueprints/main/automation/automatic_backups.yaml)

### Preface

[Generational backups :octicons-link-external-16:](https://en.wikipedia.org/wiki/Backup_rotation_scheme#Grandfather-father-son) allow you to store backups over a long period of time while still having frequent enough backups to be useful for recovery. This is done by reducing the frequency of backups as they get older. <br>

!!! info ""
    Personally I take a backup of the Home Assistant configuration every 3 hours for the first 2 days, then full backups each day for a week, and finally each week for a month.

For example, lets say my database has corrupted and I want to restore it.

If it has been less than 48 hours since it corrupted then I can restore to the exact point before it corrupted with an inaccuracy of at most 3 hours (if you're monitoring trends you don't want to lose hours worth of data, so an average accuracy of 1.5 is pretty good),

If 48 hours have passed then I can restore to any point with a maximum inaccuracy of 1 day (average accuracy of 12 hours) over the past 7 days (excluding the two where the db was corrupted).

Over a week I can restore to any point ±1 week over the past 3 weeks, while ±1 week isn't very useful for restoring a database, it can be useful for subtle thing you don't notice, like if you accidentally deleted something.

This is substantially more efficient than storing a backup every 3 hours for a month, and while you lose some accuracy as the backups get older, most failures (if they even occur) will be noticed within 48 hours,

Also, most things other than your database don't change that often so a 4-week-old backup of your home assistant config may be the same as 1 day old backup.
Also in my case the 3 hourly backup only backs up the important files to save on storage, whereas my daily/weekly backups are full backups.

Of course, you can tweak these values to your liking, or even add a month/yearly backup schedule :thumbsup:.

### Automations

```yaml title="Partial backup every 3 hours"
- alias: "AutoBackup: Hourly Backup"
  trigger: # (1)
    platform: time_pattern
    hours: "/3"
  action:
    # partial backup to save storage
    service: auto_backup.backup_partial 
    data:
      name: "AutoBackup: {{ now().strftime('%a, %-I:%M %p (%d/%m/%Y)') }}"
      addons:
        - core_mariadb
        - core_mosquitto
      folders:
        - homeassistant
        - share
        - ssl
      keep_days: 2
```

1. Automation triggers on every 3rd hour.

```yaml title="Full backup every day except Mondays"
- alias: "AutoBackup: Daily Backup"
  trigger:
    platform: time
    at: "02:30:00"
  condition:
    condition: time
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
      compressed: true
      keep_days: 7
```

```yaml title="Full backup every Monday"
- alias: "AutoBackup: Weekly Backup"
  trigger:
    platform: time
    at: "02:30:00"
  condition:
    condition: time
    weekday:
      - mon
  action:
    service: auto_backup.backup_full
    data:
      name: "WeeklyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
      compressed: true
      # store backup for a month
      # i.e. backup each week and store for 4 weeks
      keep_days: 28
```

```yaml title="Full backup on the 1st of every month"
alias: "AutoBackup: Monthly Backup"
trigger:
  # Choose a different time then your other automations
  # to ensure that two are not running at once
  - platform: time
    at: "01:00:00"
condition:
  - condition: template
    value_template: "{{ now().day == 1 }}"
action:
  - service: auto_backup.backup_full
    metadata: {}
    data:
      name: "MonthlyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
      compressed: true
      # store backup for a year
      # i.e. backup on the 1st, store for 12 months
      keep_days: 365
```

```yaml title="Full backup on the 1st of every month"
alias: "AutoBackup: Monthly Backup"
trigger:
  # Choose a different time then your other automations
  # to ensure that two are not running at once
  - platform: time
    at: "01:00:00"
condition:
  - condition: template
    value_template: "{{ now().day == 1 }}"
action:
  - service: auto_backup.backup_full
    metadata: {}
    data:
      name: "MonthlyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
      compressed: true
      # store backup for a year
      # i.e. backup on the 1st, store for 12 months
      keep_days: 365
```

```yaml title="Unified auto backup that does Daily, Weekly and Monthly in a single automation (version 2024.1 or newer required)"
alias: AutoBackup
description: Unified Auto Backups
trigger:
  - platform: time
    at: "02:30:00"
condition: []
action:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ now().day == 1 }}"
        sequence:
          - service: auto_backup.backup
            data:
              keep_days: 365
              name: "MonthlyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
      - conditions:
          - condition: time
            weekday:
              - mon
        sequence:
          - service: auto_backup.backup
            data:
              compressed: true
              keep_days: 28
              name: "WeeklyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
      - conditions:
          - condition: time
            weekday:
              - sun
              - tue
              - wed
              - thu
              - fri
              - sat
        sequence:
          - service: auto_backup.backup
            data:
              keep_days: 7
              name: "DailyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
mode: single
```
