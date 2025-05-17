"""Config flow for Dropbox integration."""

import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_FOLDER


class DropboxBackupFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Dropbox integration."""

    VERSION = 1

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
