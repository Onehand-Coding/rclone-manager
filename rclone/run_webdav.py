#!/usr/bin/env python3

import sys
import logging
import subprocess
from helper_funcs import choose_remote

# === Configuration ===
DEFAULT_PORT = 8080

REMOTE_CONFIGS = {
    "mega": {
        "--vfs-cache-mode": "writes",
        "--vfs-cache-max-size": "100M",
        "--vfs-cache-max-age": "1h"
    },
    "gdrive": {
        "--drive-shared-with-me": ""
    }
}

# === Logging Configuration ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_command(remote_name, port=DEFAULT_PORT):
    """
    Build the rclone command based on the selected remote type.
    """
    remote_type = remote_name.split()[0].lower()
    base_command = ["rclone", "serve", "webdav", f"{remote_name}:", "--addr", f"localhost:{port}"]

    remote_settings = REMOTE_CONFIGS.get(remote_type)
    if not remote_settings:
        raise ValueError(f"Unsupported remote type: {remote_type}")

    for key, value in remote_settings.items():
        base_command.append(key)
        if value:
            base_command.append(value)

    return base_command


def run(command):
    """
    Execute the rclone command with error handling.
    """
    try:
        logging.info(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True)
        logging.info("Command executed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed with return code {e.returncode}. Check your configuration.")
        sys.exit(1)
    except FileNotFoundError:
        logging.error("rclone is not installed or not found in your system PATH.")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.warning("Operation canceled by the user.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


def main():
    """
    Main function to select remote and execute the rclone command.
    """
    try:
        remote_name = choose_remote()
        command = get_command(remote_name)
        run(command)
    except ValueError as ve:
        logging.error(ve)
        sys.exit(1)
    except KeyboardInterrupt:
        logging.warning("Operation canceled by the user.")
        sys.exit(1)


if __name__ == "__main__":
    main()