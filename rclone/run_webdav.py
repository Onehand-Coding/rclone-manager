#!/usr/bin/env python3

import sys
import logging
import subprocess
from threading import Thread
from helpers import get_remote_names, choose_remote, get_remote_type, confirm

# === Configuration ===
DEFAULT_PORT = 8080

REMOTE_CONFIGS = {
    "mega": {
        "--vfs-cache-mode": "writes",
        "--vfs-cache-max-size": "100M",
        "--vfs-cache-max-age": "1h",
    },
    "drive": {
        "--drive-shared-with-me": ""
    },
    "google photos": {
        "--vfs-cache-mode": "writes"
    }
}

# === Logging Configuration ===
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_command(remote, remote_type, shared=False, port=DEFAULT_PORT):
    """Build the rclone command based on the selected remote type."""
    if shared: port +=1
    base_command = [
        "rclone",
        "serve",
        "webdav",
        f"{remote}:",
        "--addr",
        f"localhost:{port}",
    ]

    remote_settings = REMOTE_CONFIGS.get(remote_type)
    if remote_settings is None:
        raise ValueError(f"Unsupported remote type: {remote_type}")

    for key, value in remote_settings.items():
        if remote_type == "drive" and not shared:
            continue
        base_command.append(key)
        if value:
            base_command.append(value)

    return base_command


def run(command):
    """Execute the rclone command with error handling."""
    try:
        logging.info(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True)
        logging.info("Command executed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(e)
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


def serve_gdrive(remote):
    """Serve both personal and shared files for Google Drive using two configured remotes using one account."""
    shared_remote = f"{remote}-shared"
    if shared_remote not in get_remote_names():
        raise ValueError(f"No shared-remote configured for '{remote}'.")
    # Serve personal files
    personal_command = get_command(remote, remote_type="drive")
    # Serve shared files on a different port
    shared_command = get_command(shared_remote, remote_type="drive", shared=True)

    # Run both commands in separate threads
    personal_thread = Thread(target=run, args=(personal_command,))
    shared_thread = Thread(target=run, args=(shared_command,))

    personal_thread.start()
    shared_thread.start()

    personal_thread.join()
    shared_thread.join()


def main():
    """Main function to select remote and execute the rclone command."""
    try:
        print("Choose a remote to serve.")
        remote = choose_remote(get_remote_names())
        remote_type = get_remote_type(remote)
        if remote_type == "drive" and confirm("Also serve shared files?"):
                serve_gdrive(remote)
        else:
            command = get_command(remote, remote_type)
            run(command)
    except ValueError as ve:
        logging.error(ve)
        sys.exit(1)
    except KeyboardInterrupt:
        logging.warning("Operation canceled by the user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
