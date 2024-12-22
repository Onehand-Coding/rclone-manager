import sys
import json
import logging
import subprocess


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
    # Get remote names from rclone config file as json.
    result = subprocess.run(["rclone", "config", "dump"], capture_output=True, text=True)
    
    if result.returncode != 0:
        logging.error("Failed to get rclone config. Ensure rclone is installed and configured.")
        sys.exit(1)

    try:
        # Load the JSON output
        config = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse rclone config JSON: {e}")
        sys.exit(1)

    return list(config.keys())


def choose_remote():
    # Ask to choose from the configured remotes.
    print("Choose a remote:")
    remote_names = get_remote_names()
    for index, remote in enumerate(remote_names, start=1):
        print(f"{index}. {remote}")
    return remote_names[get_valid_index(remote_names) - 1]
