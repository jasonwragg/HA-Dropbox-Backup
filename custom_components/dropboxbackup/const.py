"""Constants for the backup_dropbox integration."""

from __future__ import annotations
from collections.abc import Callable

from homeassistant.util.hass_dict import HassKey

# The domain of your integration. This should match the directory name.
DOMAIN = "dropboxbackup"  # :contentReference[oaicite:0]{index=0}
CONF_FOLDER = "folder"
# Default values
DEFAULT_FOLDER = ""  # Root of the Dropbox app folder

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
