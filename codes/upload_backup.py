import os
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from utils import clear_screen, choose_from_list, is_rclone_installed, list_rclone_remotes
from config import configure_logging

logger = logging.getLogger(__name__)

def list_folders(current_path: Path) -> List[str]:
    """Lists folders in the current directory."""
    try:
        folders = sorted([f for f in os.listdir(current_path) if os.path.isdir(os.path.join(current_path, f))])
        return folders
    except PermissionError:
        print(f"Permission denied: {current_path}")
        return []
    except FileNotFoundError:
        print(f"Directory not found: {current_path}")
        return []

def navigate_local_file_system() -> str:
    """Allows the user to navigate the local file system and select a folder."""
    current_path = Path.home()  # Start from the user's home directory
    while True:
        clear_screen()
        print(f"Current Directory: {current_path}")
        folders = list_folders(current_path)
        for i, folder in enumerate(folders):
            print(f"{i + 1}. {folder}")
        print("0. Select this folder")
        print("b. Go back")
        choice = input("Enter your choice: ")

        if choice == '0':
            return str(current_path)
        elif choice == 'b':
            current_path = current_path.parent
        elif choice.isdigit() and 1 <= int(choice) <= len(folders):
            current_path = current_path / folders[int(choice) - 1]
        else:
            print("Invalid choice. Please try again.")

def list_remote_folders(remote: str) -> List[str]:
    """Lists folders in the remote directory."""
    try:
        result = subprocess.run(["rclone", "lsd", remote], capture_output=True, text=True, check=True)
        folders = [line.split()[-1] for line in result.stdout.splitlines()]
        return folders
    except subprocess.CalledProcessError as e:
        logger.error(f"Error listing remote folders: {e.stderr.strip()}")
        return []

def navigate_remote_file_system(remote: str) -> str:
    """Allows the user to navigate the remote file system and select a folder."""
    current_remote_path = remote
    while True:
        clear_screen()
        print(f"Current Remote Path: {current_remote_path}")
        folders = list_remote_folders(current_remote_path)
        for i, folder in enumerate(folders):
            print(f"{i + 1}. {folder}")
        print("0. Select this folder")
        print("b. Go back")
        print("n. Create a new folder here")
        choice = input("Enter your choice: ")

        if choice == '0':
            return current_remote_path
        elif choice == 'b':
            current_remote_path = "/".join(current_remote_path.split("/")[:-1]) or remote
        elif choice == 'n':
            new_folder = input("Enter the name of the new folder: ").strip()
            if new_folder:
                return f"{current_remote_path}/{new_folder}"
            else:
                print("Invalid folder name. Please try again.")
        elif choice.isdigit() and 1 <= int(choice) <= len(folders):
            current_remote_path = f"{current_remote_path}/{folders[int(choice) - 1]}"
        else:
            print("Invalid choice. Please try again.")

def backup_local_to_remote(local_path: str, remote_path: str) -> None:
    """Backs up a local folder to a remote using rclone."""
    command = ["rclone", "copy", local_path, remote_path, "--progress"]
    print(f"Backing up {local_path} to {remote_path}...")
    try:
        subprocess.run(command, check=True)
        print("Backup completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error during backup: {e}")

def main() -> None:
    """Main function to run the script."""
    configure_logging()
    is_rclone_installed()

    print("Welcome to the Local-to-Remote Backup Tool!")

    # Step 1: Choose a local folder to back up
    local_path = navigate_local_file_system()
    print(f"Selected local folder: {local_path}")

    # Step 2: Choose a remote
    remotes = list_rclone_remotes()
    selected_remote = choose_from_list(remotes, "\nAvailable Rclone remotes:")
    if not selected_remote:
        logger.error("No remote selected. Exiting.")
        return

    # Step 3: Choose a destination on the remote
    remote_path = navigate_remote_file_system(selected_remote)
    print(f"Selected remote destination: {remote_path}")

    # Step 4: Start the backup
    backup_local_to_remote(local_path, remote_path)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBackup process interrupted. Exiting.")