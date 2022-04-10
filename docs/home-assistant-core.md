# Home Assistant Core

To use Auto Backup on Home Assistant Core you will need to have the [`backup`](https://www.home-assistant.io/integrations/backup) integration loaded, if you are already using [`default_config`](https://www.home-assistant.io/integrations/default_config) (enabled by default) then this will already be loaded.

!!! warning
    Currently, you cannot configure the backup `name` or `password`, this may change in the future, but is due to the built-in backup integration not providing these options. Additionally, the `addons` and `folders` options are irrelevant for Home Assistant Core users.
