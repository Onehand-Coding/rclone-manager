import os
import sys
import logging
import platform
import subprocess
from pathlib import Path
from typing import List, Optional

from utils import clear_screen, choose_from_list, is_rclone_installed, get_ip_address
from config import configure_logging, DEFAULT_PORT, BACKENDS, USERNAME, PASSWORD

logger = logging.getLogger(__name__)


def list_folders(current_path: Path) -> List[str]:
    """Lists folders in the current directory."""
    try:
        folders = sorted([f for f in os.listdir(current_path) if os.path.isdir(os.path.join(current_path, f))])
        return folders
    except PermissionError:
        logger.error(f"Permission denied: {current_path}")
        return []
    except FileNotFoundError:
        logger.error(f"Directory not found: {current_path}")
        return []

def navigate_file_system() -> str:
    """Allows the user to navigate the file system and select a folder."""
    current_path = Path.home()  # Start from the user's home directory
    while True:
        clear_screen()
        print("Choose local folder to serve")
        print(f"\nCurrent Directory: {current_path}")
        folders = list_folders(current_path)
        print("[0] To select this folder")
        print("[b] To go Back")
        for i, folder in enumerate(folders):
            print(f"[{i + 1}] {folder}")
        choice = input("\nEnter your choice: ").lower()

        if choice == '0':
            return str(current_path)
        elif choice == 'b':
            current_path = current_path.parent
        elif choice.isdigit() and 1 <= int(choice) <= len(folders):
            current_path = current_path / folders[int(choice) - 1]
        else:
            print("Invalid choice. Please try again.")

def serve_local(folder_path: str, backend: str) -> None:
    """Serves the selected folder using rclone."""
    command = [
        "rclone", "serve", backend.lower(), folder_path,
        "--addr", f"{get_ip_address()}:{DEFAULT_PORT}",
        "--user", USERNAME, "--pass", PASSWORD
    ]
    logger.debug(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error: {e}")

def main() -> None:
    """Main function to run the script."""
    configure_logging()
    is_rclone_installed()
    folder_path = navigate_file_system()
    backend = choose_from_list(BACKENDS, "\nChoose backend:")
    if backend:
        serve_local(folder_path, backend)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script interrupted, Bye!")
        sys.exit()