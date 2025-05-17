"""Constants for the backup_dropbox integration."""

# The domain of your integration. This should match the directory name.
DOMAIN = "dropboxbackup"  # :contentReference[oaicite:0]{index=0}

# Configuration keys for the Config Flow and stored entry data
CONF_ACCESS_TOKEN = (
    "access_token"  # Dropbox API token :contentReference[oaicite:1]{index=1}
)
CONF_FOLDER = (
    "folder"  # Optional target folder in Dropbox :contentReference[oaicite:2]{index=2}
)

# Default values
DEFAULT_FOLDER = ""  # Root of the Dropbox app folder
