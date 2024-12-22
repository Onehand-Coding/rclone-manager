#!/usr/bin/env python3

import sys
import json
import logging
import argparse
import subprocess
from helper_funcs import get_remote_names, choose_remote


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_command(remote_name, port=8080):
    """
    Generate the appropriate rclone command based on the remote type.
    """
    remote_type = remote_name.split()[0].lower()
    base_command = ["rclone", "serve", "webdav", f"{remote_name}:", "--addr", f"localhost:{port}"]

    if remote_type == "mega":
        base_command += [
            "--vfs-cache-mode", "writes",
            "--vfs-cache-max-size", "100M",
            "--vfs-cache-max-age", "1h"
        ]
    elif remote_type == "gdrive":
        base_command.append("--drive-shared-with-me")
    else:
        raise ValueError(f"Unsupported remote type: {remote_type}")

    return base_command


def run(command):
    """
    Run the command and handle errors.
    """
    try:
        logging.debug(f"Executing command: {' '.join(command)}")
        subprocess.run(command, check=True)
        logging.info("Command executed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed with return code {e.returncode}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


def main():
    try:
        command = get_command(choose_remote())
        run(command)
    except ValueError as ve:
        logging.error(ve)
        sys.exit(1)


if __name__ == "__main__":
    main()