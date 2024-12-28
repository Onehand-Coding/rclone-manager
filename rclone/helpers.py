import sys
import json
import socket
import logging
import subprocess
from datetime import datetime


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def is_installed(tool):
    try:
        subprocess.run([tool, "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        logging.error(f"{tool} is not installed or not found in your system PATH.")
        sys.exit(1)


def confirm(prompt):
    """Prompt user for confirmation."""
    choice = ""
    while choice not in ["y", "n"]:
        choice = input(f"{prompt} (Y/n): ").lower()
    return choice == "y"


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


def get_remote_names():
    """Get remote names from rclone config file as json."""
    try:
        result = subprocess.run(
            ["rclone", "config", "dump"], capture_output=True, text=True
        )
        config = json.loads(result.stdout)
        return list(config.keys())
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to retrieve rclone remote names. {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse rclone config JSON: {e}")
        sys.exit(1)


def choose_remote(remote_names):
    print("Remotes:")
    for index, remote in enumerate(remote_names, start=1):
        print(f"{index}. {remote}")
    return remote_names[get_valid_index(remote_names) - 1]


def get_remote_type(remote):
    try:
        result = subprocess.run(["rclone", "config", "dump"], capture_output=True, check=True)
        return json.loads(result.stdout)[remote]["type"]
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to get remote type. {e}")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Error parsing config json. {e}")
        sys.exit(1)


def get_str_datetime(date_format='%B %d, %Y  %I:%M %p'):
    """Get the current date and time as a formatted string."""
    return datetime.now().strftime(date_format)