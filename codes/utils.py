import os
import re
import sys
import json
import logging
import platform
import subprocess
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

def get_ip_address() -> str:
    """Retrieves the non-loopback IP address of the machine."""
    try:
        if platform.system() == "Windows":
            output = subprocess.run(["ipconfig"], capture_output=True, text=True, check=True).stdout
            ip_matches = re.findall(r"IPv4 Address[\. ]+: (\d+\.\d+\.\d+\.\d+)", output)
        else:
            output = subprocess.run(["ip", "route", "get", "1"], capture_output=True, text=True, check=True).stdout
            ip_matches = re.findall(r"src (\d+\.\d+\.\d+\.\d+)", output)
        return ip_matches[0] if ip_matches else "127.0.0.1"
    except subprocess.CalledProcessError as e:
        logger.error(f"Error fetching IP address: {e}")
        return "127.0.0.1"

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