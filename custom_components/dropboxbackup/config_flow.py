"""Config flow for Dropbox integration."""

import logging
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

    @property
    def logger(self) -> logging.Logger:
        """Return the logger for this flow."""
        return _LOGGER

    @classmethod
    def is_matching(cls, hass, config_entry):
        """Check if the config entry matches this handler."""
        return config_entry.domain == cls.DOMAIN
