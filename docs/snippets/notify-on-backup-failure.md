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
