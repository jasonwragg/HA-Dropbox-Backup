import asyncio
import types
from types import MappingProxyType, SimpleNamespace
import sys
import os
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.loader import async_setup as loader_setup
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.config_entries import HANDLERS


async def _collect(aiter):
    return [chunk async for chunk in aiter]

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from custom_components.dropboxbackup.const import DOMAIN, DATA_BACKUP_AGENT_LISTENERS
import custom_components.dropboxbackup as integration
from custom_components.dropboxbackup.backup import (
    DropboxBackupAgent,
    CHUNK_SIZE,
    SIMPLE_UPLOAD_LIMIT,
)
from unittest.mock import Mock, AsyncMock
from homeassistant.components.backup.models import BackupAgentError
from custom_components.dropboxbackup.config_flow import DropboxOAuth2FlowHandler


@pytest.fixture
def hass(tmp_path):
    async def _create():
        hass = HomeAssistant(str(tmp_path))
        loader_setup(hass)
        hass.config_entries = ConfigEntries(hass, {})
        await hass.config_entries.async_initialize()

        async def run_job(func, *args):
            return func(*args)

        hass.async_add_executor_job = run_job
        return hass

    return asyncio.run(_create())


def _create_entry():
    return ConfigEntry(
        domain=DOMAIN,
        title="Dropbox",
        data={"token": {}},
        source="user",
        version=1,
        minor_version=1,
        options={},
        entry_id="1",
        unique_id=None,
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )


def test_migrate_entry_adds_auth_implementation(hass):
    entry = _create_entry()
    with pytest.raises(KeyError):
        _ = entry.data["auth_implementation"]

    async_update = Mock()
    hass.config_entries.async_update_entry = async_update

    result = asyncio.run(DropboxOAuth2FlowHandler.async_migrate_entry(hass, entry))
    assert result
    async_update.assert_called_once()
    data = async_update.call_args.kwargs["data"]
    assert data["auth_implementation"] == f"{DOMAIN}_{DropboxOAuth2FlowHandler.CLIENT_ID}"


def test_oauth_flow_external_step(hass):
    import custom_components.dropboxbackup.config_flow as config_flow

    HANDLERS.register(DOMAIN)(DropboxOAuth2FlowHandler)
    hass.data["components"][f"{DOMAIN}.config_flow"] = config_flow

    class DummyImpl(config_entry_oauth2_flow.LocalOAuth2Implementation):
        def __init__(self, hass):
            super().__init__(
                hass,
                DOMAIN,
                "id",
                "secret",
                "https://example.com/auth",
                "https://example.com/token",
            )

        async def _async_refresh_token(self, token):
            return token

    config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, DummyImpl(hass))

    from homeassistant.helpers import http

    class Req:
        headers = {"HA-Frontend-Base": "http://localhost:8123"}

    http.current_request.set(Req())

    result = asyncio.run(hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}))
    assert result["type"].value == "external"
    assert result["handler"] == DOMAIN
    assert "https://example.com/auth" in result["url"]


def test_setup_entry_registers_listener(hass):
    entry = _create_entry()
    called = []

    def fake_register(hass, *, listener):
        hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(lambda: called.append(True))
        return lambda: None

    with MonkeyPatch.context() as mp:
        mp.setattr(integration, "async_register_backup_agents_listener", fake_register)
        assert asyncio.run(integration.async_setup_entry(hass, entry))

    assert called == [True]


class FileMetadata:
    def __init__(self, path_lower, name, size):
        self.path_lower = path_lower
        self.name = name
        self.size = size
        self.server_modified = "2024-01-01"


@pytest.fixture
def agent(hass):
    entry = _create_entry()
    return DropboxBackupAgent(hass, entry)


def test_async_list_backups(agent, hass):
    dbx = Mock()
    file1 = FileMetadata("/backup1.tar", "backup1.tar", 1)
    result_obj = SimpleNamespace(entries=[file1], has_more=False, cursor=None)
    dbx.files_list_folder.return_value = result_obj
    with MonkeyPatch.context() as mp:
        mp.setattr(agent, "_get_dbx", AsyncMock(return_value=dbx))
        with mp.context():
            mp.setitem(sys.modules, "dropbox.files", types.SimpleNamespace(FileMetadata=FileMetadata))
            backups = asyncio.run(agent.async_list_backups())
    assert backups[0].backup_id == "backup1.tar"


def test_async_upload_backup_small(agent, hass):
    dbx = Mock()
    with MonkeyPatch.context() as mp:
        mp.setattr(agent, "_get_dbx", AsyncMock(return_value=dbx))
        async def open_stream():
            async def gen():
                yield b"data"
            return gen()
        backup = SimpleNamespace(size=10, backup_id="b.tar")
        asyncio.run(agent.async_upload_backup(open_stream=open_stream, backup=backup))
    dbx.files_upload.assert_called_once()


def test_async_upload_backup_chunked(agent, hass):
    dbx = Mock()
    with MonkeyPatch.context() as mp:
        mp.setattr(agent, "_get_dbx", AsyncMock(return_value=dbx))
        mp.setitem(
            sys.modules,
            "dropbox.files",
            types.SimpleNamespace(
                UploadSessionCursor=type(
                    "Cursor", (), {"__init__": lambda self, *a, **k: None}
                ),
                CommitInfo=type("Commit", (), {"__init__": lambda self, *a, **k: None}),
            ),
        )
        async def open_stream():
            async def gen():
                yield b"a" * (CHUNK_SIZE // 2)
                yield b"b" * (CHUNK_SIZE // 2)
                yield b"c"
            return gen()
        backup = SimpleNamespace(size=SIMPLE_UPLOAD_LIMIT + 1, backup_id="b.tar")
        asyncio.run(agent.async_upload_backup(open_stream=open_stream, backup=backup))
    dbx.files_upload_session_start.assert_called_once()
    dbx.files_upload_session_finish.assert_called_once()


def test_async_download_backup(agent, hass):
    dbx = Mock()
    dbx.files_download.return_value = (None, SimpleNamespace(content=b"abc"))
    with MonkeyPatch.context() as mp:
        mp.setattr(agent, "_get_dbx", AsyncMock(return_value=dbx))
        stream = asyncio.run(agent.async_download_backup("backup1.tar"))
        data = b"".join([chunk for chunk in asyncio.run(_collect(stream))])
    assert data == b"abc"


def test_async_delete_backup(agent, hass):
    dbx = Mock()
    with MonkeyPatch.context() as mp:
        mp.setattr(agent, "_get_dbx", AsyncMock(return_value=dbx))
        asyncio.run(agent.async_delete_backup("backup1.tar"))
    dbx.files_delete_v2.assert_called_once()


def test_async_get_backup(agent, hass):
    dbx = Mock()
    meta = SimpleNamespace(name="backup1.tar", size=1, server_modified="2024-01-01")
    dbx.files_get_metadata.return_value = meta
    with MonkeyPatch.context() as mp:
        mp.setattr(agent, "_get_dbx", AsyncMock(return_value=dbx))
        result = asyncio.run(agent.async_get_backup("backup1.tar"))
    assert result.name == "backup1.tar"


def test_backup_agent_error(agent, hass):
    dbx = Mock()
    dbx.files_list_folder.side_effect = Exception
    with MonkeyPatch.context() as mp:
        mp.setattr(agent, "_get_dbx", AsyncMock(return_value=dbx))
        with mp.context():
            mp.setitem(sys.modules, "dropbox.files", types.SimpleNamespace(FileMetadata=FileMetadata))
            with pytest.raises(BackupAgentError):
                asyncio.run(agent.async_list_backups())
