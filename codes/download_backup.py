import os
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from utils import clear_screen, choose_from_list, is_rclone_installed, list_rclone_remotes, list_local_folders
from config import configure_logging

logger = logging.getLogger(__name__)

def list_remote_files_and_folders(remote: str) -> List[str]:
    """Lists files and folders in the remote directory."""
    try:
        result = subprocess.run(["rclone", "lsf", remote], capture_output=True, text=True, check=True)
        items = [line.strip() for line in result.stdout.splitlines()]
        return items
    except subprocess.CalledProcessError as e:
        logger.error(f"Error listing remote files and folders: {e.stderr.strip()}")
        return []

def navigate_remote_file_system(remote: str) -> str:
    """Allows the user to navigate the remote file system and select a file or folder."""
    current_remote_path = remote
    while True:
        clear_screen()
        print(f"Current Remote Path: {current_remote_path}")
        items = list_remote_files_and_folders(current_remote_path)
        for i, item in enumerate(items):
            print(f"{i + 1}. {item}")
        print("0. Select this location")
        print("b. Go back")
        choice = input("Enter your choice: ")

        if choice == '0':
            return current_remote_path
        elif choice == 'b':
            current_remote_path = "/".join(current_remote_path.split("/")[:-1]) or remote
        elif choice.isdigit() and 1 <= int(choice) <= len(items):
            selected_item = items[int(choice) - 1]
            current_remote_path = f"{current_remote_path}/{selected_item}"
        else:
            print("Invalid choice. Please try again.")


def navigate_local_file_system() -> str:
    """Allows the user to navigate the local file system and select a destination."""
    current_path = Path.home()  # Start from the user's home directory
    while True:
        clear_screen()
        print(f"Current Directory: {current_path}")
        folders = list_local_folders(current_path)
        for i, folder in enumerate(folders):
            print(f"{i + 1}. {folder}")
        print("0. Select this folder")
        print("b. Go back")
        print("n. Create a new folder here")
        choice = input("Enter your choice: ")

        if choice == '0':
            return str(current_path)
        elif choice == 'b':
            current_path = current_path.parent
        elif choice == 'n':
            new_folder = input("Enter the name of the new folder: ").strip()
            if new_folder:
                new_folder_path = current_path / new_folder
                new_folder_path.mkdir(exist_ok=True)
                return str(new_folder_path)
            else:
                print("Invalid folder name. Please try again.")
        elif choice.isdigit() and 1 <= int(choice) <= len(folders):
            current_path = current_path / folders[int(choice) - 1]
        else:
            print("Invalid choice. Please try again.")

def download_remote_to_local(remote_path: str, local_path: str) -> None:
    """Downloads a remote file or folder to a local destination using rclone."""
    command = ["rclone", "copy", remote_path, local_path, "--progress"]
    print(f"Downloading {remote_path} to {local_path}...")
    try:
        subprocess.run(command, check=True)
        print("Download completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error during download: {e}")

def main() -> None:
    """Main function to run the script."""
    configure_logging()
    is_rclone_installed()

    print("Welcome to the Remote-to-Local Download Tool!")

    # Step 1: Choose a remote
    remotes = list_rclone_remotes()
    selected_remote = choose_from_list(remotes, "\nAvailable Rclone remotes:")
    if not selected_remote:
        logger.error("No remote selected. Exiting.")
        return

    # Step 2: Choose a file or folder on the remote
    remote_path = navigate_remote_file_system(selected_remote)
    print(f"Selected remote file/folder: {remote_path}")

    # Step 3: Choose a local destination
    local_path = navigate_local_file_system()
    print(f"Selected local destination: {local_path}")

    # Step 4: Start the download
    download_remote_to_local(remote_path, local_path)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDownload process interrupted. Exiting.")