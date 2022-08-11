# Services

Services are the core of Auto Backup, they are the only methods that cause Auto Backup to do anything.

## `auto_backup.backup`

Create a full or partial backup.

This is the primary method and includes the functionality of the `backup_full` and `backup_partial` services.

| Parameter                                    | Description                                                                               | Type     | Example                                                     |
| -------------------------------------------- | ----------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------- |
| `name`                                       | Optional name, defaults to the current date and time.                                     | `string` | `#!jinja Automatic Backup {{ now().strftime('%Y-%m-%d') }}` |
| [`include_addons`](#addon-and-folder-names)  | List of addons to include in the backup (name or slug). Wildcards supported for slugs.    | `list`   | `#!json ["Almond", "glances", "core_mariadb", "core_*"]`    |
| [`include_folders`](#addon-and-folder-names) | List of folders to include in the backup.                                                 | `list`   | `#!json ["Local add-ons", "homeassistant", "share"]`        |
| [`exclude_addons`](#addon-and-folder-names)  | List of addons to exclude from the backup (name or slug).  Wildcards supported for slugs. | `list`   | `#!json ["Almond", "glances", "core_mariadb", "core_*"]`    |
| [`exclude_folders`](#addon-and-folder-names) | List of folders to exclude from the backup.                                               | `list`   | `#!json ["Local add-ons", "homeassistant", "share"]`        |
| `password`                                   | Optional password to secure backup.                                                       | `string` | `#!json 1234`                                               |
| [`keep_days`](#keep-days)                    | The number of days to keep the backup.                                                    | `float`  | `#!json 2`                                                  |
| [`download_path`](#download-path)            | Locations to download the backup to after creation.                                       | `list`   | `#!json ["/usb_drive"]`                                     |

??? example "Create a full backup"

    ```yaml
    service: auto_backup.backup
    data:
      name: "Full Backup"
      keep_days: 2
    ```

??? example "Create a partial backup"

    ```yaml title="Partial backup including just the config folder"
    service: auto_backup.backup
    data:
      name: "Partial Backup"
      include_folders:
        - config
      keep_days: 2
    ```

??? example "Create an empty partial backup"

    ```yaml
    service: auto_backup.backup
    data:
      name: "Partial Backup"
      include: {}
      keep_days: 2
    ```

??? example "Alternate include/exclude config"

    ```yaml
    service: auto_backup.backup
    data:
      name: "Partial Backup"
      include:
        addons: [...]
        folders: [...]
      exclude:
        addons: [...]
        folders: [...]
      keep_days: 2
    ```

### Addon and folder names

**Addon names** are case-insensitive and can be the addon name/title, these are the same names seen when creating a partial backup through the Supervisor backups page. They can also be the addons slug (slug must be lowercase). You can also use wildcards for matching slugs, such as `core_*` to include all core addons.

**Folder names** are also case-insensitive and use the names seen when creating a partial backup through the Supervisor backups page.
Currently, accepted values are (ignoring case):

- `ssl`
- `share`
- `media`
- `addons` or `local add-ons` or `addons/local`
- `config` or `home assistant configuration` or `homeassistant`

### Keep Days

The `keep_days` parameter allows you to specify how long the backup should be kept for before being deleted. Default is forever. You can specify a float value for keep days, e.g. to keep a backup for 12 hours use `0.5`.

### Download Path

The `download_path` parameter allows you to specify a location or of list of locations to download the backup to after creation. This directory must be accessible from Home Assistant. If you are running in docker your paths will be relative to the container for example your Home Assistant configuration directory is stored under `/config` and the share folder is under `/share`.

!!! tip
    The backup will still be stored under `/backup` and show up on the [backups](https://my.home-assistant.io/redirect/backup) page, it will only be copied/downloaded to the location specified, to immediately delete the backup use a negative value for `keep_days` (e.g. `#!yaml keep_days: -1` ).

!!! info
    A slugified version of the backups name will be used for the filename, if a file with that name already exists the backups id (slug) will be used instead.

!!! note
    When running on **Home Assistant Core** backups will be copied not downloaded. When running **Home Assistant Supervised** integrations do not have direct access to the `/backup` folder, which is why the backup is downloaded and not simply copied.


## `auto_backup.backup_full`

Create a full backup with optional exclusions.

| Parameter                         | Description                                           | Type                                | Example                                                                                                                      |
| --------------------------------- | ----------------------------------------------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `name`                            | Optional name, defaults to the current date and time. | `string`                            | `#!jinja Automatic Backup {{ now().strftime('%Y-%m-%d') }}`                                                                  |
| `exclude`                         | Addons/Folders to exclude from the backup.            | [`Exclude Object`](#exclude-object) | [`#!json {"addons": ["MariaDB"], "folders": ["Local add-ons", "share"]}`](examples.md#excluding-addonsfolders-from-a-backup) |
| `password`                        | Optional password to secure backup.                   | `string`                            | `#!json 1234`                                                                                                                |
| [`keep_days`](#keep-days)         | The number of days to keep the backup.                | `float`                             | `#!json 2`                                                                                                                   |
| [`download_path`](#download-path) | Locations to download the backup to after creation.   | `list`                              | `#!json ["/usb_drive"]`                                                                                                      |

#### Exclude Object

| Parameter                            | Description                                               | Type   | Example                                              |
| ------------------------------------ | --------------------------------------------------------- | ------ | ---------------------------------------------------- |
| [`addons`](#addon-and-folder-names)  | List of addons to exclude from the backup (name or slug). | `list` | `#!json ["Almond", "glances", "core_mariadb"]`       |
| [`folders`](#addon-and-folder-names) | List of folders to exclude from the backup.               | `list` | `#!json ["Local add-ons", "homeassistant", "share"]` |

## `auto_backup.backup_partial`

Create a partial backup.

| Parameter                            | Description                                           | Type     | Example                                                     |
| ------------------------------------ | ----------------------------------------------------- | -------- | ----------------------------------------------------------- |
| `name`                               | Optional name, defaults to the current date and time. | `string` | `#!jinja Automatic Backup {{ now().strftime('%Y-%m-%d') }}` |
| [`addons`](#addon-and-folder-names)  | List of addons to backup (name or slug).              | `list`   | `#!json ["Almond", "glances", "core_mariadb"]`              |
| [`folders`](#addon-and-folder-names) | List of folders to backup.                            | `list`   | `#!json ["Local add-ons", "homeassistant", "share"]`        |
| `password`                           | Optional password to secure backup.                   | `string` | `#!json 1234`                                               |
| [`keep_days`](#keep-days)            | The number of days to keep the backup.                | `float`  | `#!json 2`                                                  |
| [`download_path`](#download-path)    | Locations to download the backup to after creation.   | `list`   | `#!json ["/usb_drive"]`                                     |

## `auto_backup.purge`

Purge expired backups.

There are no parameters here, just call the service, and it will remove any expired backups.

This service is useful if you want to manually specify when to purge backups,
such as doing a batch delete at 12AM.

!!! info
    Expired backups are automatically purged when creating new backups, this can be disabled in the [options menu](index.md#options).
