| Event                           | Event Data                                  |
| ------------------------------- | ------------------------------------------- |
| `auto_backup.backup_start`      | `#!json {"name": "NAME"}`                   |
| `auto_backup.backup_successful` | `#!json {"name": "NAME", "slug": "SLUG"}`   |
| `auto_backup.backup_failed`     | `#!json {"name": "NAME", "error": "ERROR"}` |
| `auto_backup.purged_backups`    | `#!json {"backups": ["SLUG"]}`              |

## Example Automation Using Events

--8<-- "docs/snippets/notify-on-backup-failure.md"
