"""Config flow for Dropbox integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_FOLDER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Optional(CONF_FOLDER, default=""): str,
    }
)


class DropboxBackupFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Dropbox integration."""

    VERSION = 4

    @staticmethod
    async def async_migrate_entry(hass, config_entry):
        """Migrate old config entries to new schema."""
        version = config_entry.version

        # if coming from version 1 or 2, we don't need to change data,
        # we just bump the version so HA will accept it.
        if version < DropboxBackupFlow.VERSION:
            # (you could transform config_entry.data here if needed)
            hass.config_entries.async_update_entry(
                config_entry,
                data=config_entry.data,
                options=config_entry.options,
                version=DropboxBackupFlow.VERSION,
            )

        return True

    @classmethod
    def is_matching(cls, dict_) -> bool:
        """Test if entry matches dict."""
        return True

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Optional(CONF_FOLDER, default=""): str,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        return self.async_create_entry(
            title="Dropbox Backup",
            data=user_input,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DropboxBackupOptionsFlow(config_entry)


class DropboxBackupOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Dropbox Backup integration."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Show the form to update token/folder."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Pre-fill with current values
        schema = DATA_SCHEMA.extend(
            {
                vol.Required(
                    CONF_ACCESS_TOKEN,
                    default=self.config_entry.data[CONF_ACCESS_TOKEN],
                ): str,
                vol.Optional(
                    CONF_FOLDER,
                    default=self.config_entry.data.get(CONF_FOLDER, ""),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
