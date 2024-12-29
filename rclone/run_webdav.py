#!/usr/bin/env python3

import sys
import json
import logging
import subprocess
from pathlib import Path
from threading import Thread
from configs import DEFAULT_PORT
from manage_webdav_config import load_configuration
from helpers import get_remote_names, choose_remote, get_remote_type, confirm

# === Logging Configuration === #
logger = logging.getLogger(__name__)


def add_authentication(command, username, password):
    """Add authentication flags to command to add security."""
    return command + ["--user", username, "--pass", password]


def get_command(remote, remote_type, shared=False, add_auth=False, port=DEFAULT_PORT):
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

    remote_settings = load_configuration().get(remote_type)
    if remote_settings is None:
        raise ValueError(f"Unsupported remote type: {remote_type}")

    for key, value in remote_settings.items():
        if remote_type == "drive" and not shared:
            continue
        base_command.append(key)
        if value:
            base_command.append(value)

    return add_authentication(base_command, username="Admin", password="47153N") if add_auth else base_command


def run(command):
    """Execute the rclone command with error handling."""
    try:
        logger.debug(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True)
    except KeyboardInterrupt:
        logger.warning("Operation canceled by the user.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(e)
        sys.exit(1)
    except FileNotFoundError:
        logger.error("rclone is not installed or not found in your system PATH.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


def serve_gdrive(remote, authenticate):
    """Serve both personal and shared files for Google Drive using two configured remotes with thesame gdrive account."""
    shared_remote = f"{remote}-shared"
    if shared_remote not in get_remote_names():
        raise ValueError(f"No shared-remote configured for '{remote}'.")
    # Serve personal files
    personal_command = get_command(remote, remote_type="drive", shared=False, add_auth=authenticate)
    # Serve shared files on a different port
    shared_command = get_command(shared_remote, remote_type="drive", shared=True, add_auth=authenticate)

    # Run both commands in separate threads
    personal_thread = Thread(target=run, args=(personal_command,))
    shared_thread = Thread(target=run, args=(shared_command,))

    personal_thread.start()
    shared_thread.start()

    personal_thread.join()
    shared_thread.join()


def main():
    """Main function to setup remote and execute the rclone webdav commands."""
    try:
        print("Choose a remote to serve.")
        remote = choose_remote(get_remote_names())
        authenticate = confirm("Add authentication?")
        remote_type = get_remote_type(remote)
        if remote_type == "drive" and confirm("Serve shared files?"):
                serve_gdrive(remote, authenticate)
        else:
            command = get_command(remote, remote_type, add_auth=authenticate)
            run(command)
    except ValueError as ve:
        logger.error(ve)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by the user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
