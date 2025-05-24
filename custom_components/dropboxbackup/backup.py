"""Dropbox Backup Agent for Home Assistant."""

import logging
import urllib.parse

from homeassistant.components.backup import BackupAgent, BackupAgentError, AgentBackup
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.config_entry_oauth2_flow import (
    async_get_config_entry_implementation,
)
from .const import DOMAIN, CONF_FOLDER


_LOGGER = logging.getLogger(__name__)

# Dropbox recommends 4 MB chunks for upload sessions.
CHUNK_SIZE = 4 * 1024 * 1024
# Files up to 150 MB can be uploaded in a single call.
SIMPLE_UPLOAD_LIMIT = 150 * 1024 * 1024


class DropboxBackupAgent(BackupAgent):
    """This module provides a BackupAgent implementation that interacts with Dropbox to list."""

    domain = DOMAIN
    name = "Dropbox"
    unique_id = "dropbox_backup"

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.folder = entry.data.get(CONF_FOLDER, "").strip("/")
        self._dbx = None

    async def _get_dbx(self):
        """Return a Dropbox client with a fresh access token."""
        # Always refresh the token to avoid using an expired one
        impl = await async_get_config_entry_implementation(self.hass, self.entry)
        _LOGGER.debug("Got OAuth2 impl: %s", impl)  # ②

        # 2) Show entire config entry data
        _LOGGER.debug("Config entry data: %s", self.entry.data)  # ③

        # 3) Pull token dict from entry.data
        token_data = self.entry.data.get("token")
        _LOGGER.debug("Token dict before refresh: %s", token_data)  # ④

        if not token_data:
            _LOGGER.error("No token_data found under entry.data['token']")  # ⑤
            raise BackupAgentError("OAuth2 token not found in config entry")

        try:
            # 4) Refresh token (new signature takes only token_data)
            session = await impl.async_refresh_token(token_data)
            _LOGGER.debug(
                "Session returned by async_refresh_token: %s", session
            )  # ⑥

            # Persist the refreshed token so future calls use the new values
            new_data = {**self.entry.data, "token": session}
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        except Exception as e:
            _LOGGER.error("async_refresh_token failed: %s", e, exc_info=True)  # ⑦
            raise

        access_token = session.get("access_token")
        _LOGGER.debug("Using access_token: %s…", access_token[:8])  # ⑧

        # 5) Lazy-import Dropbox SDK
        import dropbox

        dbx = dropbox.Dropbox(oauth2_access_token=access_token)  # ⑨
        self._dbx = dbx
        _LOGGER.info("Dropbox client instantiated successfully")  # ⑩
        return dbx

    async def async_list_backups(self, **kwargs) -> list[AgentBackup]:
        """List all backups in the configured Dropbox folder."""
        # Build the Dropbox path
        folder = self.folder.strip("/") if self.folder else ""
        dbx_path = f"/{folder}" if folder else ""
        all_entries = []

        try:
            # Lazily get a valid Dropbox client (with a fresh token)
            dbx = await self._get_dbx()

            # List the first page
            result = await self.hass.async_add_executor_job(
                dbx.files_list_folder, dbx_path
            )
            all_entries.extend(result.entries)

            # Continue paging until done
            while result.has_more:
                result = await self.hass.async_add_executor_job(
                    dbx.files_list_folder_continue, result.cursor
                )
                all_entries.extend(result.entries)

            # Convert to HA AgentBackup objects
            backups: list[AgentBackup] = []
            for entry in all_entries:
                # Lazy‐check FileMetadata
                from dropbox.files import FileMetadata

                if not isinstance(entry, FileMetadata):
                    continue

                ui_id = entry.path_lower.lstrip("/")
                backups.append(
                    AgentBackup(
                        addons=[],
                        backup_id=ui_id,
                        date=entry.server_modified,
                        database_included=True,
                        extra_metadata={},
                        folders=[],
                        homeassistant_included=True,
                        homeassistant_version=getattr(self.hass, "version", ""),
                        name=entry.name,
                        protected=False,
                        size=entry.size,
                    )
                )
            return backups

        except Exception as err:
            _LOGGER.error(
                "Dropbox list_backups failed for path '%s': %s",
                dbx_path,
                err,
                exc_info=True,
            )
            raise BackupAgentError from err

    async def async_upload_backup(self, *, open_stream, backup, **kwargs) -> None:
        """Upload a snapshot using the most efficient Dropbox API."""
        decoded = urllib.parse.unquote(backup.backup_id)
        path = f"/{decoded}"
        _LOGGER.debug("Uploading backup to %s", path)

        try:
            dbx = await self._get_dbx()

            stream = await open_stream()

            # For small files we can upload in a single request
            if backup.size <= SIMPLE_UPLOAD_LIMIT:
                data = bytearray()
                async for chunk in stream:
                    data.extend(chunk)

                await self.hass.async_add_executor_job(
                    dbx.files_upload,
                    bytes(data),
                    path,
                )
                _LOGGER.info("Uploaded %s in one request (%d bytes)", path, backup.size)
                return

            # Otherwise use an upload session
            first_chunk = await stream.__anext__()
            session_start = await self.hass.async_add_executor_job(
                dbx.files_upload_session_start,
                first_chunk,
            )
            session_id = session_start.session_id
            offset = len(first_chunk)

            from dropbox.files import UploadSessionCursor, CommitInfo

            buffer = bytearray()
            async for chunk in stream:
                buffer.extend(chunk)
                if len(buffer) >= CHUNK_SIZE:
                    cursor = UploadSessionCursor(session_id, offset)
                    await self.hass.async_add_executor_job(
                        dbx.files_upload_session_append_v2,
                        bytes(buffer),
                        cursor,
                    )
                    offset += len(buffer)
                    buffer.clear()

            cursor = UploadSessionCursor(session_id, offset)
            commit = CommitInfo(path)
            await self.hass.async_add_executor_job(
                dbx.files_upload_session_finish,
                bytes(buffer),
                cursor,
                commit,
            )
            offset += len(buffer)

            _LOGGER.info("Completed chunked upload for %s (%d bytes)", path, offset)

        except StopAsyncIteration:
            _LOGGER.error("No data received from open_stream for upload of %s", path)
            raise BackupAgentError("Empty upload stream") from None

        except Exception as err:
            _LOGGER.error("Chunked upload failed for %s: %s", path, err, exc_info=True)
            raise BackupAgentError from err

    async def async_download_backup(self, backup_id: str, **kwargs):
        """
        Return an async iterator of bytes for the given backup_id.
        HA will await this coroutine to get the iterator.
        """
        # Decode any percent‐encoding from the UI
        decoded = urllib.parse.unquote(backup_id)
        path = f"/{decoded}"
        _LOGGER.debug("Starting Dropbox download for %s", path)

        try:
            dbx = await self._get_dbx()
            # Download the full content in a thread
            metadata, response = await self.hass.async_add_executor_job(
                dbx.files_download, path
            )
            content = response.content
        except Exception as err:
            _LOGGER.error(
                "Dropbox download failed for %s: %s", path, err, exc_info=True
            )
            raise BackupAgentError from err

        # Inner async generator for streaming chunks
        async def _stream():
            chunk_size = 1024 * 1024
            for offset in range(0, len(content), chunk_size):
                yield content[offset : offset + chunk_size]

        return _stream()

    async def async_delete_backup(self, backup_id: str, **kwargs) -> None:
        """Delete by path."""
        path = f"/{backup_id}"
        _LOGGER.debug("Deleting Dropbox backup %s", path)
        try:
            dbx = await self._get_dbx()
            await self.hass.async_add_executor_job(dbx.files_delete_v2, path)
        except Exception as err:
            _LOGGER.error("Dropbox delete failed for %s: %s", path, err, exc_info=True)
            raise BackupAgentError from err

    async def async_get_backup(self, backup_id: str, **kwargs) -> AgentBackup:
        """Fetch one snapshot’s metadata by URL-decoding the ID first."""
        # Decode any %20, %2F, etc. back to real characters
        decoded = urllib.parse.unquote(backup_id)
        path = f"/{decoded}"
        _LOGGER.debug("Decoded backup_id %s → %s", backup_id, path)
        try:
            dbx = await self._get_dbx()
            meta = await self.hass.async_add_executor_job(dbx.files_get_metadata, path)
            return AgentBackup(
                addons=[],
                backup_id=backup_id,
                date=meta.server_modified,
                database_included=True,
                extra_metadata={},
                folders=[],
                homeassistant_included=True,
                homeassistant_version=getattr(self.hass, "version", ""),
                name=meta.name,
                protected=False,
                size=meta.size,
            )
        except Exception as err:
            _LOGGER.error(
                "Dropbox get_backup failed for %s: %s", path, err, exc_info=True
            )
            raise BackupAgentError from err


async def async_get_backup_agents(hass: HomeAssistant):
    """Return all configured DropboxBackupAgent instances."""
    agents = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        agents.append(DropboxBackupAgent(hass, entry))
    return agents


@callback
def async_register_backup_agents_listener(hass: HomeAssistant, *, listener):
    """Async call to get agaent listeners"""

    hass.data.setdefault(f"{DOMAIN}_listeners", []).append(listener)

    @callback
    def remove():
        hass.data[f"{DOMAIN}_listeners"].remove(listener)

    return remove
