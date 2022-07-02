???+ blueprint "Blueprint"
    Send notifications based on events created by the [Auto Backup](https://jcwillox.github.io/hass-auto-backup) integration, such as when a backup fails.

    [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A//raw.githubusercontent.com/jcwillox/home-assistant-blueprints/main/automation/notify_auto_backup.yaml)

```yaml title="Notify on Backup Failure"
- alias: "Notify Backup Failure"
  trigger:
    platform: event
    event_type: auto_backup.backup_failed # (1)
  action:
    service: persistent_notification.create # (2)
    data:
      title: "Backup Failed."
      message: |-
        Name: {{ trigger.event.data.name }}
        Error: {{ trigger.event.data.error }}
```

1. We listen for the `auto_backup.backup_failed` event.
2. Create a persistent notification on failure with the backups name and the error.
