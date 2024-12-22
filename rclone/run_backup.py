#!/usr/bin/env python3

import sys
import logging
import subprocess
from pathlib import Path
from helper_funcs import get_valid_index, choose_remote

# Configure logging for informative output and errors
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Local main folder
LOCAL_SOURCE = Path("/storage/emulated/0").absolute()


def contains_subfolder(parent_folder):
    """Check if a folder contains subfolder(s)."""
    return any(file.is_dir() for file in parent_folder.iterdir())


def confirm(question, /, *, choices="(Y/n)", confirm_letter='y'):
    """Prompt user for confirmation."""
    return input(f"{question} {choices} ").lower().strip().startswith(confirm_letter)


def choose_folder(parent_folder):
    """Choose a folder inside the specified folder."""
    folders = [file for file in parent_folder.iterdir() if file.is_dir() and not file.name.startswith(".")]
    if not folders:
        logging.warning(f"No folders found in {parent_folder}.")
        sys.exit(1)

    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.name}")

    return folders[get_valid_index(folders) - 1]


def get_local_path():
    """Choose a local folder to backup."""
    logging.info("Selecting a folder to backup...")
    chosen_folder = choose_folder(LOCAL_SOURCE)

    while contains_subfolder(chosen_folder) and confirm(f"'{chosen_folder.name}' contains subfolders. Go deeper?"):
        logging.info(f"Exploring subfolders in '{chosen_folder.name}'...")
        chosen_folder = choose_folder(chosen_folder)

    if not confirm(f"Backup '{chosen_folder.name}'?"):
        logging.info("Backup operation cancelled by user.")
        sys.exit(0)

    logging.info(f"Selected folder: {chosen_folder}")
    return chosen_folder


def get_remote_path(remote_name):
    """Display remote folders if available, and allow choosing or default to root."""
    try:
        logging.info("Fetching remote folders...")
        result = subprocess.run(
            ["rclone", "lsd", f"{remote_name}:"],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to list remote folders: {e}")
        sys.exit(1)

    # Parse folder list
    folders = [line.split()[-1] for line in result.stdout.strip().split('\n') if line]

    if not folders:
        logging.warning("No folders found on the remote.")
        if confirm("Do you want to place the backup in the root folder instead?"):
            remote_path = f"{remote_name}:/"
            logging.info(f"Backup will be placed in the root folder: {remote_path}")
            return remote_path
        else:
            logging.info("Backup operation canceled by the user.")
            sys.exit(0)

    # Display folders
    print("Available folders on the remote:")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder}")

    print("0. Place backup in the root folder")

    # Allow root selection
    selected_index = get_valid_index(folders, allow_root=True) - 1

    if selected_index == -1:
        remote_path = f"{remote_name}:/"
        logging.info(f"Backup will be placed in the root folder: {remote_path}")
    else:
        remote_folder = folders[selected_index]
        remote_path = f"{remote_name}:/{remote_folder}"
        logging.info(f"Selected remote folder: {remote_path}")

    return remote_path


def execute_backup(local_path, remote_path):
    """Backup a specific folder using rclone."""
    logging.info(f"Starting backup: '{local_path}' → '{remote_path}'")
    try:
        subprocess.run(
            ["rclone", "copy", str(local_path), remote_path, "--progress"],
            check=True
        )
        logging.info(f"Backup completed successfully: '{local_path}' → '{remote_path}'")
    except subprocess.CalledProcessError as e:
        logging.error(f"Backup failed: {e}")
        sys.exit(1)


def main():
    try:
        local_path = get_local_path()
        remote_name = choose_remote()
        remote_path = get_remote_path(remote_name)
        execute_backup(local_path, remote_path)
    except KeyboardInterrupt:
        logging.warning("\nOperation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()