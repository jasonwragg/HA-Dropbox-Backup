"""The Dropbox Backup integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .backup import async_register_backup_agents_listener
from .const import DATA_BACKUP_AGENT_LISTENERS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dropbox Backup and register for backup agent updates."""

    # Notify function drives the BackupManager to reload agents
    def _notify() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    # Register and ensure cleanup
    remove = async_register_backup_agents_listener(hass, listener=_notify)
    entry.async_on_unload(remove)

    # Fire immediately to register your agent
    _notify()

    return True
