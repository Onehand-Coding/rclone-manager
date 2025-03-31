import os
import re
import sys
import json
import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def is_rclone_installed() -> bool:
    """Check if rclone is installed in the system."""
    try:
        subprocess.run(["rclone", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        logger.error("Rclone is not installed or not found in your system PATH.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error checking rclone installation: {e}")
        return False

def get_ip_address() -> Optional[str]:
    """Get the best available IP (prioritizes hotspot if available)."""
    try:
        if platform.system() == "Windows":
            # Windows: Use ipconfig
            output = subprocess.run(
                ["ipconfig"], 
                capture_output=True, 
                text=True, 
                check=True
            ).stdout
            ip_matches = re.findall(
                r"IPv4 Address[\. ]+: (\d+\.\d+\.\d+\.\d+)", 
                output, 
                flags=re.IGNORECASE
            )
        else:
            # Unix-like: Use `ip route` (modern) or `ifconfig` (fallback)
            try:
                # Try `ip route` first (best for Termux)
                output = subprocess.run(
                    ["ip", "route", "get", "1"], 
                    capture_output=True, 
                    text=True, 
                    check=True
                ).stdout
                ip_matches = re.findall(r"src (\d+\.\d+\.\d+\.\d+)", output)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to `ifconfig` (older systems)
                output = subprocess.run(
                    ["ifconfig"], 
                    capture_output=True, 
                    text=True, 
                    check=True
                ).stdout
                ip_matches = re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", output)

        # Filter out loopback (127.0.0.1) and link-local (169.254.x.x)
        valid_ips = [
            ip for ip in ip_matches 
            if not ip.startswith("127.") 
            and not ip.startswith("169.254.")
        ]

        # Prioritize hotspot IP (192.168.x.x)
        for ip in valid_ips:
            if ip.startswith("192.168."):
                return ip  # Hotspot IP found!

        # Return the first valid IP if no hotspot found
        return valid_ips[0] if valid_ips else None

    except Exception:
        return None  # No network? Return None instead of 127.0.0.1


def clear_screen() -> None:
    """Clears the terminal screen."""
    os.system('cls' if platform.system() == "Windows" else 'clear')


def choose_from_list(items: List[str], prompt: str) -> Optional[str]:
    """Prompts the user to choose an item from a list."""
    if not items:
        logger.warning("No items available to choose from.")
        return None

    print(prompt)
    for i, item in enumerate(items):
        print(f"[{i + 1}] {item}")
    while True:
        choice = input("\nEnter your choice: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            return items[int(choice) - 1]
        print("Invalid choice. Please enter a valid number.")


def list_rclone_remotes() -> List[str]:
    """Lists available rclone remotes."""
    try:
        output = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, check=True)
        remotes = [remote.strip() for remote in output.stdout.splitlines() if "shared" not in remote]
        return sorted(remotes)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error retrieving Rclone remotes: {e.stderr.strip()}")
        return []


def list_local_folders(current_path: Path) -> List[str]:
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


def navigate_local_file_system() -> str:
    """Allows the user to navigate the file system and select a folder."""
    current_path = Path.home()  # Start from the user's home directory
    while True:
        clear_screen()
        print("Choose a local folder")
        print(f"\nCurrent Directory: {current_path}")
        folders = list_local_folders(current_path)
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