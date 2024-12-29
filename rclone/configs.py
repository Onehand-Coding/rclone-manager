from pathlib import Path

HOME_DIR = Path(__file__).parent
CONFIG_FILE =HOME_DIR / "remote-commands-config.json"
LOG_FILE = HOME_DIR / "logs.txt"
DEFAULT_PORT = 8080
LOCAL_SOURCE = Path("/storage/emulated/0").absolute()