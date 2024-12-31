import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(verbose=True)


class MissingCredentialError(Exception):
    """Raised if a credential is not found in .env file."""


def get_credential(key):
    credential = os.getenv(key)
    if credential is None:
        raise MissingCredentialError(f"Missing {key} item in .env file.")
    return credential


WEBDAV_USERNAME = get_credential("WEBDAV_USERNAME")
WEBDAV_PASSWORD = get_credential("WEBDAV_PASSWORD")
HOME_DIR = Path(__file__).parent
CONFIG_FILE = HOME_DIR / "remote-commands-config.json"
LOG_FILE = HOME_DIR / "logs.txt"
DEFAULT_PORT = 8080
LOCAL_SOURCE = Path("/storage/emulated/0").absolute()