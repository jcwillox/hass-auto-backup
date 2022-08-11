# Home Assistant Core

To use Auto Backup on Home Assistant Core you will need to have the [`backup`](https://www.home-assistant.io/integrations/backup) integration loaded, if you are already using [`default_config`](https://www.home-assistant.io/integrations/default_config) (enabled by default) then this will already be loaded.

!!! note
    Currently, you cannot configure the backup `password`, this may change in the future, but is due to the built-in backup integration not providing this option. Additionally, the `addons` and `folders` options are irrelevant for Home Assistant Core users.

!!! warning
    Currently, the `name` option is not natively supported on Home Assistant Core. Auto Backup, however, provides a patch that enables this functionality through its service calls.
    
    The patch is only temporarily enabled when attempting to create a backup with a custom name, if you do not specify the `name` field for any of Auto Backup's services the patch wont be applied. This is an experimental feature, and while the implementation is fairly robust if you experience any issues you can stop using the `name` field and [report an issue](https://github.com/jcwillox/hass-auto-backup/issues/new/choose) on GitHub.