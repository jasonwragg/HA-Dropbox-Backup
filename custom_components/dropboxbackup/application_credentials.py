"""The Dropbox Backup integration."""

from homeassistant.core import HomeAssistant
from homeassistant.components.application_credentials import AuthorizationServer


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return the authorization server for Dropbox Backup."""
    return AuthorizationServer(
        authorize_url="https://www.dropbox.com/oauth2/authorize",
        token_url="https://api.dropboxapi.com/oauth2/token",
    )
