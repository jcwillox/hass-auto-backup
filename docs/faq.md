# FAQ

## How does this differ from the automatic backups added in Home Assistant 2025.1?

The addition of configurable automatic backups in Home Assistant 2025.1 is a great addition, but it is not quite yet as powerful or customisable as Auto Backup and lacks some features that Auto Backup provides, including:

-   Full control over when backups are taken and deleted, what's included, and retention.
    -   This allows us to support [generational backup](advanced-examples.md#generational-backups) schemes, which HA does not support. You would need the ability to set up multiple automatic backup configuration, currently you are limited to just one.
    -   Support for wildcard [includes and excludes](services.md) for addons and folders.
    -   Support for using [addon names instead of slugs](services.md#addon-and-folder-names).
-   Support for unencrypted backups.
    -   HA now has mandatory encryption, which is probably a good thing for the majority of users, but it has certain limitations, such as not being able to open backup archives and view individual files. HA doesn't provide a method to explore or decrypt backups without restoring them. So if you want to go back and look at your `configuration.yaml` file from a year ago it will be difficult. Additionally, encryption is only needed if you are uploading your backups directly to an insecure location.
-   [Sensors](sensors.md) for tracking the state of backups.
-   Success and failure [events](events.md) for when backups are started/created/failed/deleted.
    -   This also allows you to run actions after a backup is created.
-   [Download a backup](services.md#download-path) to a specified directory after completion (for example a usb drive).
    -   This can partially be done with the custom locations feature, but some users have found cases where that does not work as it does not support local file paths and only support network storages currently.
