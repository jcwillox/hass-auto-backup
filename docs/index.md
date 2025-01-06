# Overview

Auto Backup is an Improved Backup Service for Home Assistant that can Automatically Remove Backups and Supports Generational Backup Schemes.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jcwillox&repository=hass-auto-backup&category=integration)

!!! important ""

    While Home Assistant does provide built-in services for creating backups, they do not provide the ability to exclude items from a backup, or advanced retention settings, this custom integration aims to fix that. See the [FAQ](faq.md) for more information on differences.

## Features

-   [x] Provides more advanced and configurable [service calls](services.md).
-   [x] [Exclude addons/folders](services.md) from a backup.
-   [x] [Automatically delete backups](services.md#keep-days) after an individually specified amount of time.
-   [x] Backup to [custom locations](services.md#custom-locations) such as network storage.
-   [x] [Download backups](services.md#download-path) to a specified directory after completion (for example a usb drive).
-   [x] Allows the use of [addon names instead of slugs](services.md#addon-and-folder-names).
-   [x] Provides a [sensor](sensors.md) to monitor the status of your backups.
-   [x] Creates [events](events.md) for when backups are started/created/failed/deleted.
-   [x] Supports [generational backup](advanced-examples.md#generational-backups) schemes.
-   [x] Supports unencrypted and encrypted backups, including the default encryption added in 2025.1 see [#181](https://github.com/jcwillox/hass-auto-backup/issues/181).

## Blueprints

???+ blueprint "Blueprint: Automatic Backups"

    Create backups each day and keep them for a configurable amount of time, backups are stored less frequently the older they are.

    [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A//raw.githubusercontent.com/jcwillox/home-assistant-blueprints/main/automation/automatic_backups.yaml)

???+ blueprint "Blueprint: Notifications"

    Send notifications based on events created by the [Auto Backup](https://jcwillox.github.io/hass-auto-backup) integration, such as when a backup fails.

    [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A//raw.githubusercontent.com/jcwillox/home-assistant-blueprints/main/automation/notify_auto_backup.yaml)

## Configuration

After installing Auto Backup via [HACS](https://hacs.xyz), it can then be setup via the UI, by going to **Configuration** → **Devices & Services** → **Add Integration** → **Auto Backup** or by clicking the button below.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=auto_backup)

### Options

| Option                               | Description                                                                                                                                                                                                  |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Automatically delete expired backups | This option will automatically purge any expired backups when creating a new backup.                                                                                                                         |
| Backup Timeout                       | You can increase this value if you get timeout errors when creating a backup. This can happen with very large backups. Increasing this might make Auto Backup less reliable at monitoring backups to delete. |

---

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/jcwillox)
