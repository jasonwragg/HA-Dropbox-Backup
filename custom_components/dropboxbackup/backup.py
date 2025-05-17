"""Dropbox Backup Agent for Home Assistant."""

import logging
import urllib.parse
import dropbox
from dropbox.files import FileMetadata
from homeassistant.components.backup import BackupAgent, BackupAgentError, AgentBackup
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_FOLDER


_LOGGER = logging.getLogger(__name__)


class DropboxBackupAgent(BackupAgent):
    """This module provides a BackupAgent implementation that interacts with Dropbox to list, upload, download, and delete backup files in a configured Dropbox folder."""

    domain = DOMAIN
    name = "Dropbox"
    unique_id = "dropbox_backup"

    def __init__(self, hass: HomeAssistant, token: str, folder: str):
        self.hass = hass
        self.dbx = dropbox.Dropbox(
            token
        )  # uses Dropbox Python SDK :contentReference[oaicite:10]{index=10}
        self.folder = folder.strip("/")

    async def async_list_backups(self, **kwargs) -> list[AgentBackup]:
        folder = self.folder.strip("/") if self.folder else ""
        dbx_path = f"/{folder}" if folder else ""
        all_entries = []

        try:
            result = await self.hass.async_add_executor_job(
                self.dbx.files_list_folder, dbx_path
            )
            all_entries.extend(result.entries)
            while result.has_more:
                result = await self.hass.async_add_executor_job(
                    self.dbx.files_list_folder_continue, result.cursor
                )
                all_entries.extend(result.entries)

            backups: list[AgentBackup] = []
            for entry in all_entries:
                if not isinstance(entry, FileMetadata):
                    continue

                # strip leading slash for HA’s ID
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
        """Uploads a snapshot in chunks using Dropbox upload sessions."""

        # Decode the HA UI ID back to a valid path
        decoded = urllib.parse.unquote(backup.backup_id)
        path = f"/{decoded}"
        _LOGGER.debug("Uploading large backup to %s in chunks", path)

        # Dropbox recommends 150 MB chunks max; choose e.g. 8 MB:
        # CHUNK_SIZE = 8 * 1024 * 1024

        try:
            # 1) Open the HA snapshot stream
            stream = await open_stream()

            # 2) Read the first chunk and start a session
            first_chunk = await stream.anext()  # get first async chunk
            session_start_res = await self.hass.async_add_executor_job(
                self.dbx.files_upload_session_start, first_chunk
            )
            session_id = session_start_res.session_id
            offset = len(first_chunk)

            # 3) Append all full chunks
            async for chunk in stream:
                await self.hass.async_add_executor_job(
                    self.dbx.files_upload_session_append_v2,
                    chunk,
                    dropbox.files.UploadSessionCursor(session_id, offset),
                )
                offset += len(chunk)

            # 4) Finish the session, committing to the target path
            commit = dropbox.files.CommitInfo(path)
            await self.hass.async_add_executor_job(
                self.dbx.files_upload_session_finish,
                b"",  # no extra data since all appended
                dropbox.files.UploadSessionCursor(session_id, offset),
                commit,
            )

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
            # Download the full content in a thread
            metadata, response = await self.hass.async_add_executor_job(
                self.dbx.files_download, path
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
            await self.hass.async_add_executor_job(self.dbx.files_delete_v2, path)
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
            meta = await self.hass.async_add_executor_job(
                self.dbx.files_get_metadata, path
            )
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
    """Gets the backup agents"""

    agents = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        token = entry.data[CONF_ACCESS_TOKEN]
        folder = entry.data.get(CONF_FOLDER, "")
        agents.append(DropboxBackupAgent(hass, token, folder))
    return agents


@callback
def async_register_backup_agents_listener(hass: HomeAssistant, *, listener):
    """Async call to get agaent listeners"""

    hass.data.setdefault(f"{DOMAIN}_listeners", []).append(listener)

    def remove():
        hass.data[f"{DOMAIN}_listeners"].remove(listener)

    return remove
