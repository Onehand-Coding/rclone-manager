#!/usr/bin/env python3
import os
import re
import sys
import json
import subprocess
import threading
import platform
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from logging.handlers import RotatingFileHandler

# Constants
ROOT_DIR = Path(__file__).parent.parent
CONFIG_FILE = ROOT_DIR / "data" / "config.json"
LOG_FILE = ROOT_DIR / "logs" /"remotes.log"
DEFAULT_CONFIG = {
    "flags": {
        "drive": {},
        "mega": {},
        "http": {},
        "webdav": {},
        "ftp": {},
        "sftp": {}
    }
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3), logging.StreamHandler(sys.stdout)])

# Cache for configuration data
_config_cache: Optional[Dict[str, Any]] = None


def list_rclone_remotes() -> List[str]:
    """Lists available rclone remotes, excluding those containing 'shared'.

    Returns:
        List[str]: A list of available remotes.
    """
    try:
        output = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, check=True)
        remotes = [remote.strip() for remote in output.stdout.splitlines() if "shared" not in remote]
        return sorted(remotes)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error retrieving Rclone remotes: {e.stderr.strip()}")
        return []


def choose_from_list(items: List[str], prompt: str) -> Optional[str]:
    """Prompts the user to choose an item from the provided list.

    Args:
        items (List[str]): List of items to choose from.
        prompt (str): Prompt message to display.

    Returns:
        Optional[str]: The selected item, or None if no valid choice is made.
    """
    print(prompt)
    for i, item in enumerate(items):
        print(f"[{i + 1}] {item}")
    while True:
        choice = input("\nChoose an option (number): ").strip()
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(items):
                return items[index]
        print("Invalid choice. Please enter a valid number or name.")


def get_ip_address() -> str:
    """Retrieves the non-loopback IP address of the machine using platform-specific commands.

    Returns:
        str: The IP address, or an error message if unable to fetch.
    """
    try:
        if platform.system() == "Windows":
            # Use ipconfig on Windows
            output = subprocess.run(["ipconfig"], capture_output=True, text=True, check=True).stdout
            ip_matches = re.findall(r"IPv4 Address[\. ]+: (\d+\.\d+\.\d+\.\d+)", output)
        else:
            # Use `ip route` on Unix-like systems
            output = subprocess.run(["ip", "route", "get", "1"], capture_output=True, text=True, check=True).stdout
            ip_matches = re.findall(r"src (\d+\.\d+\.\d+\.\d+)", output)

        if ip_matches:
            return ip_matches[0]  # Return the first match
        else:
            return "127.0.0.1"  # Fallback to localhost
    except subprocess.CalledProcessError as e:
        logging.error(f"Error fetching IP address: {e}")
        return "127.0.0.1"


def get_remote_type(remote: str) -> Optional[str]:
    """Gets the type of remote from rclone config.

    Args:
        remote (str): The remote name.

    Returns:
        Optional[str]: The remote type, or None if not found.
    """
    try:
        remote_name = remote.rstrip(':')
        result = subprocess.run(["rclone", "config", "dump"], capture_output=True, text=True, check=True)
        config = json.loads(result.stdout)
        return config.get(remote_name, {}).get("type")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to get rclone remotes configuration: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse rclone config JSON: {e}")
        return None
    except Exception as e:
        logging.error(f"Error in get_remote_type: {e}")
        return None


def load_config() -> Dict[str, Any]:
    """Loads the configuration from the config file.

    Returns:
        Dict[str, Any]: The configuration data.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not CONFIG_FILE.exists():
        logging.info("Config file 'config.json' not found. Creating a default one.")
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        _config_cache = DEFAULT_CONFIG
    else:
        with open(CONFIG_FILE, "r") as f:
            _config_cache = json.load(f)
    return _config_cache


def get_flags(remote_type: str, shared: bool = False) -> List[str]:
    """Get flags from config file for the specified remote type.

    Args:
        remote_type (str): The type of remote.
        shared (bool): Whether the remote is shared.

    Returns:
        List[str]: A list of flags.
    """
    config = load_config()
    if "flags" not in config or remote_type not in config["flags"]:
        logging.warning(f"No flags configured for remote type: {remote_type}")
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


def serve_remote(remote: str, backend: str, port: int, shared: bool = False, user: str = "admin", passw: str = "admin"):
    """Starts an rclone serve process in a new thread.

    Args:
        remote (str): The remote name.
        backend (str): The backend to use.
        port (int): The port to serve on.
        shared (bool): Whether the remote is shared.
        user (str): The username for authentication.
        passw (str): The password for authentication.
    """
    remote_name = f"{remote.strip(':')}-shared:" if shared else remote
    remote_type = get_remote_type(remote_name)
    logging.debug(f"Remote type for {remote_name}: {remote_type}")

    flags = get_flags(remote_type, shared) if remote_type else []
    command = ["rclone", "serve", backend, remote_name, "--addr", f"{get_ip_address()}:{port}", "--user", user, "--pass", passw]
    command.extend(flags)

    logging.info(f"Starting Rclone serve for: {remote_name} using {backend} on port {port}")
    logging.debug(f"Running: {' '.join(command)}")

    try:
        subprocess.run(command, check=True)
    except Exception as e:
        logging.error(f"Error running rclone serve: {e}")


def main():
    """Main function to run the script."""
    remotes = list_rclone_remotes()
    selected_remote = choose_from_list(remotes, "\nAvailable Rclone remotes:")
    if not selected_remote:
        logging.error("No remote selected. Exiting.")
        sys.exit(1)

    backends = ["http", "webdav", "ftp", "sftp"]
    selected_backend = choose_from_list(backends, "\nAvailable backends:")
    if not selected_backend:
        logging.error("No backend selected. Exiting.")
        sys.exit(1)

    remote_type = get_remote_type(selected_remote)
    if remote_type == "drive":
        logging.info("Drive remote detected, starting two instances (normal and shared)...")
        thread1 = threading.Thread(target=serve_remote, args=(selected_remote, selected_backend, 8080), daemon=True)
        thread2 = threading.Thread(target=serve_remote, args=(selected_remote, selected_backend, 9090, True), daemon=True)
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
    else:
        serve_remote(selected_remote, selected_backend, 8080)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Bye!")
        sys.exit()