# Backup to Dropbox

A Home Assistant custom integration that adds a **Dropbox** backup agent to the native Backup UI, allowing you to create, list, download, and delete snapshots directly from your Dropbox account.

---

## Features

- **Full BackupAgent Support**: Implements all core methods—`async_list_backups`, `async_upload_backup`, `async_download_backup`, `async_delete_backup`—integrating deeply with Home Assistant’s Backup system.
- **Config Flow**: Authenticate with Dropbox using OAuth 2 via Home Assistant Application Credentials.
- **Pagination Handling**: Correctly pages through Dropbox folder listings to show every snapshot.
- **Error Logging**: Provides detailed debug logs for upload, download, and metadata operations.

---

## Requirements

- **Home Assistant Core 2025.1+** (Backup Agents API introduced in 2025.1).
- A Dropbox **Scoped Access** app with an App key and secret, and the following scopes enabled:
  - `files.content.write`
  - `files.content.read`
  - `files.metadata.read`.
- **HACS** (Home Assistant Community Store) for easy installation (optional).

---

## Installation

### Via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jasonwragg&repository=HA-Dropbox-Backup&category=integration)

1. In Home Assistant, open **HACS** in the sidebar.
2. Click the **⋮** menu (top right) and select **Custom repositories**.
3. Add this repository:
   - **URL**: `https://github.com/jasonwragg/HA-Dropbox-Backup`
   - **Category**: **Integration**
4. Back in **HACS → Integrations**, locate **Backup to Dropbox** and click **Install**.
5. After installation, go to **Settings → System → Integrations**, click **+ Add integration**, then search for **Dropbox Backup**.

### Manual

1. Clone into your HA config directory:
   ```bash
   mkdir -p /config/custom_components/backup_dropbox
   git clone https://github.com/jasonwragg/HA-Dropbox-Backup.git      /config/custom_components/backup_dropbox
   ```
2. Restart Home Assistant.
3. Navigate to **Settings → System → Integrations**, click **+ Add integration**, and search for **Dropbox Backup**.

---

## Configuration

### 1. Create a Dropbox App

1. Go to the [Dropbox App Console](https://www.dropbox.com/developers/apps).
2. Click **Create app**, choose **Scoped access**, then select **App folder** or **Full Dropbox**.
3. Under **Permissions**, enable:
   - `files.content.write`
   - `files.content.read`
   - `files.metadata.read`.
4. Note your **App key** and **App secret** from the app overview page.

### 2. Add Application Credentials and Authorize

1. In Home Assistant, open **Settings → System → Application Credentials**.
2. Click **Add Credential**, set **Name** to `dropbox`, and enter your **App key** and **App secret**.
3. Then open **Settings → System → Integrations**, click **+ Add integration**, search for **Dropbox Backup**, and follow the OAuth sign-in flow.
4. After granting Dropbox access, click **Submit**, then **Finish**.

---

## Usage

- **Create Backup**: **Settings → System → Backups → Create**, choose **Dropbox**, and follow prompts.
- **List Backups**: Dropbox-stored snapshots appear automatically in the list.
- **Restore**: Select a Dropbox snapshot, click **Restore**, and follow the wizard.
- **Delete**: Use the three-dot menu on any Dropbox backup entry and choose **Delete**.

---

## Troubleshooting

- **`missing_scope` errors**: Ensure your Dropbox app has the required scopes enabled, then reauthorize the integration.
- **No backups listed**: Verify the **Folder** path matches your Dropbox folder and contains `.tar` snapshots.
- **UI 404 errors**: Avoid illegal characters in folder names and ensure IDs are URL-decoded properly.

---

## Contributing

Contributions are welcome! Please fork this repo, follow Home Assistant’s [integration quality guidelines](https://developers.home-assistant.io/docs/integration_quality_scale/), and submit a pull request.

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
