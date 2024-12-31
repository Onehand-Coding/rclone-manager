import sys
import json
import socket
import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)


def find_free_port():
    """Find unused port to use dynamic port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def is_installed(tool):
    """Check if a program is indtalled in the system."""
    try:
        subprocess.run([tool, "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        logger.error(f"{tool} is not installed or not found in your system PATH.")
        sys.exit(1)


def confirm(prompt):
    """Prompt user for confirmation."""
    choice = ""
    try:
        while choice not in ["y", "n"]:
            choice = input(f"{prompt} (Y/n): ").lower()
        return choice == "y"
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        sys.exit(0)


def get_valid_index(item_list, allow_root=False):
    """Get valid integer input from user."""
    while True:
        try:
            valid_num = int(input("> "))
            if allow_root and valid_num == 0:
                return valid_num
            if 1 <= valid_num <= len(item_list):
                return valid_num
            else:
                print("Please enter a valid number from the list.")
        except ValueError:
            print("Please enter an integer.")
        except KeyboardInterrupt:
            logger.info("Operation cancelled by user.")
            sys.exit(0)


def choose_remote():
    """Lets user choose a remote from the available remotes."""
    try:
        logger.info("Selecting remote.")
        print("Available remotes:")
        remote_names = list(get_rclone_config().keys())
        if not remote_names:
            logger.error("No remotes found in rclone config.")
            sys.exit(1)
        
        for index, remote in enumerate(remote_names, start=1):
            print(f"{index}. {remote}")
        
        selected_index = get_valid_index(remote_names)
        return remote_names[selected_index - 1]
    except Exception as e:
        logger.error(f"Error selecting remote: {e}")
        sys.exit(1)


def get_str_datetime(date_format='%B %d, %Y  %I:%M %p'):
    """Get the current date and time as string based on the provided format."""
    return datetime.now().strftime(date_format)


def get_rclone_config():
    """Get the current rclone remotes configuration as JSON."""
    try:
        result = subprocess.run(["rclone", "config", "dump"], capture_output=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get rclone remotes configuration. {e}")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Failed to  parse rclone config JSON. {e}")
        sys.exit(1)