## Send a notification on backup failure

--8<-- "docs/snippets/notify-on-backup-failure.md"

## Scheduling automatic backups

Perform a partial backup of the Home Assistant config folder, mariadb and mosquitto every 3 hours,
and store each backup for 2 days.

```yaml title="Automatic Backups"
- alias: Automatic Backup
  trigger: # (1)
    - platform: time_pattern
      hours: "/3"
  action:
    - service: auto_backup.backup_partial
      data:
        name: "AutoBackup: {{ now().strftime('%a, %-I:%M %p (%d/%m/%Y)') }}"
        addons:
          - almond
          - Glances
          - mosquitto broker
          - core_mariadb
        folders:
          - homeassistant
          - Share
          - ssl
          - Local add-ons
        keep_days: 2
```

1. Automation triggers on every 3rd hour.

## Excluding addons/folders from a backup

```yaml title="Exclude from Backup"
- alias: Perform Daily Backup
  trigger:
    - platform: time
      at: "00:00:00"
  action:
    - service: auto_backup.backup_full
      data:
        name: "DailyBackup: {{ now().strftime('%A, %B %-d, %Y') }}"
        keep_days: 7
        exclude:
          addons:
            - Portainer
          folders:
            - Local add-ons
            - share
```
