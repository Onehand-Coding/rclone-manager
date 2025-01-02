import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(verbose=True, override=True)

class MissingCredentialError(Exception):
    """Raised if a credential is not found in .env file."""

def get_credential(key):
    """Fetch a credential from environment variables or raise an error if missing."""
    credential = os.getenv(key)
    if credential is None:
        raise MissingCredentialError(
            f"Missing {key} in .env file. Please add {key} to continue."
        )
    return credential

# Fetch sensitive credentials
WEBDAV_USERNAME = get_credential("WEBDAV_USERNAME")
WEBDAV_PASSWORD = get_credential("WEBDAV_PASSWORD")

# Paths and default configurations
HOME_DIR = Path(os.getenv("HOME_DIR", Path(__file__).parent))
CONFIG_FILE = HOME_DIR / os.getenv("CONFIG_FILE", "remote-commands-config.json")
LOG_FILE = HOME_DIR / os.getenv("LOG_FILE", "logs.txt")
DEFAULT_PORT = int(os.getenv("DEFAULT_PORT", 8080))
LOCAL_SOURCE = Path(os.getenv("LOCAL_SOURCE", "/storage/emulated/0")).absolute()