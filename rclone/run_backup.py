#!/usr/bin/env python3

import sys
import logging
import subprocess
from pathlib import Path
from configs import LOCAL_SOURCE
from helpers import get_valid_index, choose_remote, get_remote_names, confirm

# logging configuration
logger = logging.getLogger(__name__)


def is_hidden(file):
    """Checks if a file is hidden."""
    return file.name.startswith(".") and not file.name in (".", "..")


def contains_hidden(folder):
    """Checks if a folder and its subfolders contains hidden items."""
    return any(is_hidden(file) for file in folder.rglob(".*"))


def list_hidden(folder):
    """Display hidden files contained in a folder."""
    hidden_files = [file for file in folder.rglob(".*") if is_hidden(file)]
    n_items = len(hidden_files)
    s_items = "items" if n_items >= 2 else "item"
    print(f"\n{n_items} Hidden {s_items} found:")
    for hidden_file in hidden_files:
        print(hidden_file.name)
    print()


def contains_subfolder(folder):
    """Check if a folder contains subfolder(s)."""
    return any(file.is_dir() and not is_hidden(file) for file in folder.iterdir())


def choose_folder(parent_folder):
    """Choose a folder inside a specified folder."""
    subfolders = sorted(
        [
            file
            for file in parent_folder.iterdir()
            if file.is_dir() and not is_hidden(file)
        ]
    )
    if not subfolders:
        logger.warning(f"No folders found in {parent_folder}.")
        sys.exit(1)
    
    print("\nSelect a folder:\n")
    for index, folder in enumerate(subfolders, start=1):
        print(f"{index}. {folder.name}")

    return subfolders[get_valid_index(subfolders) - 1]


def get_local_path():
    """Choose a local folder to backup."""
    logger.info("Selecting a folder to backup...")
    chosen_folder = choose_folder(LOCAL_SOURCE)

    while contains_subfolder(chosen_folder) and confirm(
        f"'{chosen_folder.name}' contains subfolders. Go deeper?"
    ):
        logger.info(f"Exploring subfolders in '{chosen_folder.name}'...")
        chosen_folder = choose_folder(chosen_folder)

    if not confirm(f"Backup '{chosen_folder.name}'?"):
        logger.info("Backup operation cancelled by user.")
        sys.exit(0)

    logger.info(f"Selected folder: {chosen_folder}")
    return chosen_folder


def get_remote_folders(remote):
    """Get remote folders from remote."""
    try:
        logger.info("Fetching remote folders...")
        result = subprocess.run(
            ["rclone", "lsd", f"{remote}:"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to list remote folders: {e}")
        sys.exit(1)

    # Parse folder list
    remote_folders = sorted(
        [line.split()[-1] for line in result.stdout.strip().split("\n") if line]
    )

    return remote_folders


def get_remote_path(remote, remote_folders):
    """Allow user to choose from remote folders if available, create one if needed or default to root."""
    if not remote_folders:
        logging.warning("No folders found in remote.")
        if confirm("Create a new folder to use?"):
            folder_name = input("Enter new folder name: ").strip()
            remote_path = f"{remote}:/{folder_name}"
            logger.info(f"Backup will be placed in {remote_path}")
            return remote_path
        elif confirm("Do you want to place the backup in the root folder instead?"):
            remote_path = f"{remote}:/"
            logger.info(f"Backup will be placed in the root folder: {remote_path}")
            return remote_path
        else:
            logger.info("Backup operation canceled by the user.")
            sys.exit(0)

    # Display folders
    print("Available folders on remote:")
    print("0. Root folder")
    for index, folder in enumerate(remote_folders, start=1):
        print(f"{index}. {folder}")

    # Allow root folder selection
    folder_index = get_valid_index(remote_folders, allow_root=True) - 1

    if folder_index == -1:
        remote_path = f"{remote}:/"
        logger.info(f"Backup will be placed in root folder: {remote_path}")
    else:
        remote_folder = remote_folders[folder_index]
        remote_path = f"{remote}:/{remote_folder}"
        logger.info(f"Selected remote folder: {remote_path}")

    return remote_path


def execute_backup(local_path, remote_path, include_hidden=False):
    """Backup a specific folder using rclone."""
    logger.info(f"Starting backup: '{local_path}' → '{remote_path}'")
    command = ["rclone", "copy", str(local_path), remote_path, "--progress"]
    # Exlude all hidden files recursively.
    if not include_hidden:
        command += ["--exclude", "/**/.*"]
    try:
        logging.debug(f"Executing command: {' '.join(command)}")
        subprocess.run(command, check=True)
        logger.info(f"Backup completed successfully: '{local_path}' → '{remote_path}'")
    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


def main():
    try:
        local_path = get_local_path()
        if contains_hidden(local_path):
            list_hidden(local_path)
            include_hidden = confirm("Include hidden items in backup?")
        print("\nChoose a remote destination.\n")
        remote_names = get_remote_names()
        remote = choose_remote(remote_names)
        remote_folders = get_remote_folders(remote)
        remote_path = get_remote_path(remote, remote_folders)
        execute_backup(local_path, remote_path, include_hidden)
    except KeyboardInterrupt:
        logger.warning("\nOperation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
