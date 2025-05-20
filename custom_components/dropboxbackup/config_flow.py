"""Config flow for Dropbox integration."""

import logging
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DropboxOAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle OAuth2 for Dropbox Backup via Application Credentials."""

    DOMAIN = DOMAIN
    CLIENT_ID = "dropbox"  # must match the 'auth' name in manifest.json
    SCOPE = [
        "files.content.read",
        "files.content.write",
        "files.metadata.read",
    ]
    extra_authorize_data = {
        "token_access_type": "offline",
        "force_reapprove": "true",  # ensure Dropbox re-prompts
    }

    @staticmethod
    async def async_migrate_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Migrate old entries that lack 'auth_implementation'."""
        if "auth_implementation" not in entry.data:
            # Build new data dict with the required key
            new_data = {
                **entry.data,
                # The default ID that HA gives the first implementation object
                # It’s always   f\"{DOMAIN}_{CLIENT_ID}\"   when you use Application Credentials
                "auth_implementation": f"{DOMAIN}_{DropboxOAuth2FlowHandler.CLIENT_ID}",
            }
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.info(
                "Dropbox Backup: migrated config entry %s – added auth_implementation",
                entry.entry_id,
            )
        # Return True → Home Assistant continues setting up the entry
        return True

    @property
    def logger(self) -> logging.Logger:
        """Return the logger for this flow."""
        return _LOGGER

    @classmethod
    def is_matching(cls, hass, config_entry):
        """Check if the config entry matches this handler."""
        return config_entry.domain == cls.DOMAIN
