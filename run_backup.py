#!/usr/bin/env python3

import sys
import json
import logging
import subprocess
from pathlib import Path
from helper_funcs import get_valid_index, choose_remote

# Configure logging for informative output and errors
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s-%(levelname)s- %(message)s"
)

# Local main folder
LOCAL_SOURCE = Path("/storage/emulated/0").absolute()


def contains_subfolder(parent_folder):
    """Checks if a folder contains subfolder/s."""
    return  any(file.is_dir() for file in parent_folder.iterdir())


def confirm(question, /, *, choice="(Y/n)", confirm_letter='y'):
    """Prompt user for confirmation."""
    return input(f"{question} {choice} ").lower().strip().startswith(confirm_letter)


def choose_folder(parent_folder):
   """Choose a folder inside a folder."""
   folders = [file for file in parent_folder.iterdir() if file.is_dir() and not file.name.startswith(".")]
   for index, folder in enumerate(folders, start=1):
       print(f"{index}. {folder.name}")
    
   return folders[get_valid_index(folders) - 1]


def get_local_path():
    """Choose a local folder to backup."""
    print("Choose a folder to backup.")
    chosen_folder = choose_folder(LOCAL_SOURCE)
    
    # If user chooses a folder that contains subfolder/s, ask if they want to go deeper to choose a subfolder.
    while contains_subfolder(chosen_folder) and confirm(f"{chosen_folder.name} contains subfolder, go deeper? "):
        print(f"Folders inside {chosen_folder.name}:")
        print("Enter a number to select the folder")
        chosen_folder =choose_folder(chosen_folder)
    if not confirm(f"Backup {chosen_folder.name}"):
        logging.info(f"You didn't choose a folder to backup!")
        sys.exit()
    return chosen_folder
    
    
def get_remote_path(remote_name):
    """Get the destination path from remote."""
    print(f"Choose a path to place your backup.")
    remote_folders = subprocess.run(["rclone", "lsd", f"{remote_name}"], capture_output=True).stdout.decode()
    path = choose_folder(remote_folders)
    
    return f"{remote_name}:/{path}"


def execute_backup(local_path, remote_path):
    """Backup a specific folder using rclone."""
    logging.info(f"Backing up '{local_path.name}' to '{remote_path}:'...")
    try:
        subprocess.run(
            ["rclone", "copy", str(local_path), f"{remote_path}", "--progress"],
            check=True
        )
        logging.info(f"Backup of '{local_path.name}' completed successfully.\n")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error backing up '{local_path}': {e}")


def main():
    # Set up remote, and folders.
    local_path = get_local_path()
    remote_name = choose_remote()
    remote_path = get_remote_path(remote_name)
    # Execute backup.
    execute_backup(local_path, remote_path)


if __name__ == "__main__":
    main()