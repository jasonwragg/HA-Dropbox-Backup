import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_FOLDER


class DropboxBackupFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
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
