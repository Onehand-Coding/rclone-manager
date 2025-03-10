import sys
import json
import logging
import subprocess
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

from utils import get_ip_address, choose_from_list, is_rclone_installed
from config import configure_logging, CONFIG_FILE, DEFAULT_CONFIG, DEFAULT_PORT, USERNAME, PASSWORD, BACKENDS

logger = logging.getLogger(__name__)

# Cache for configuration data
_config_cache: Optional[Dict[str, Any]] = None

def list_rclone_remotes() -> List[str]:
    """Lists available rclone remotes."""
    try:
        output = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, check=True)
        remotes = [remote.strip() for remote in output.stdout.splitlines() if "shared" not in remote]
        return sorted(remotes)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error retrieving Rclone remotes: {e.stderr.strip()}")
        return []

def get_remote_type(remote: str) -> Optional[str]:
    """Gets the type of remote from rclone config."""
    try:
        remote_name = remote.rstrip(':')
        result = subprocess.run(["rclone", "config", "dump"], capture_output=True, text=True, check=True)
        config = json.loads(result.stdout)
        return config.get(remote_name, {}).get("type")
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error(f"Failed to get remote type: {e}")
        return None

def load_config() -> Dict[str, Any]:
    """Loads the configuration from the config file."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not CONFIG_FILE.exists():
        logger.info("Config file not found. Creating a default one.")
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        _config_cache = DEFAULT_CONFIG
    else:
        with open(CONFIG_FILE, "r") as f:
            _config_cache = json.load(f)
    return _config_cache

def get_flags(remote_type: str, shared: bool = False) -> List[str]:
    """Gets flags from config file for the specified remote type."""
    config = load_config()
    if "flags" not in config or remote_type not in config["flags"]:
        logger.warning(f"No flags configured for remote type: {remote_type}")
        return []

    flag_configs = config["flags"][remote_type]
    flags = []
    for key, value in flag_configs.items():
        if remote_type == "drive" and not shared:
            continue
        flags.append(key)
        if value:
            flags.append(value)
    return flags

def serve_remote(remote: str, backend: str, port: int = DEFAULT_PORT, shared: bool = False, user: str = USERNAME, passw: str = PASSWORD) -> None:
    """Starts an rclone serve process in a new thread."""
    remote_name = f"{remote.strip(':')}-shared:" if shared else remote
    remote_type = get_remote_type(remote_name)
    logger.debug(f"Remote type for {remote_name}: {remote_type}")

    flags = get_flags(remote_type, shared) if remote_type else []
    command = [
        "rclone", "serve", backend.lower(), remote_name,
        "--addr", f"{get_ip_address()}:{port}",
        "--user", user, "--pass", passw
    ]
    command.extend(flags)
    logger.debug(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except Exception as e:
        logger.error(f"Error running rclone serve: {e}")

def main() -> None:
    """Main function to run the script."""
    configure_logging()
    is_rclone_installed()

    remotes = list_rclone_remotes()
    selected_remote = choose_from_list(remotes, "\nChoose remote:")
    if not selected_remote:
        logger.error("No remote selected. Exiting.")
        sys.exit(1)

    selected_backend = choose_from_list(BACKENDS, "\nChoose backend:")
    if not selected_backend:
        logger.error("No backend selected. Exiting.")
        sys.exit(1)

    remote_type = get_remote_type(selected_remote)
    if remote_type == "drive":
        logger.info("Drive remote detected, starting two instances (normal and shared)...")
        thread1 = threading.Thread(target=serve_remote, args=(selected_remote, selected_backend), daemon=True)
        thread2 = threading.Thread(target=serve_remote, args=(selected_remote, selected_backend, DEFAULT_PORT + 1, True), daemon=True)
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
    else:
        serve_remote(selected_remote, selected_backend)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script interrupted, Bye!")
        sys.exit()