#!/usr/bin/env python3

import sys
import json
import logging
from pathlib import Path
from pprint import pprint
from configs import CONFIG_FILE
from helpers import confirm, get_valid_index, get_rclone_config

# === Logging Configuration === #
logger = logging.getLogger(__name__)

# Define the actions that the user can take in the menu
ACTIONS = [
    {"Add New Configuration": lambda: add_configuration()},
    {"Edit Existing Configurations": lambda: edit_configuration()},
    {"View Existing Configurations": lambda: display_configuration()},
    {"Delete Configuration": lambda: delete_configuration()},
    {"Back to Main Menu": None},
]

def load_configuration():
    """Load remote configurations from the JSON file."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            configs = json.load(f)
        return configs
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Failed to load configuration file: {e}")
        sys.exit(1)

def save_configuration(configs):
    """Save the updated configuration back to the JSON file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(configs, f, indent=4)
        logger.info("Configuration saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        sys.exit(1)

def display_configuration():
    """Display the currently configured remote types."""
    configs = load_configuration()
    logger.info("Current remote type flag configurations:")
    pprint(configs)

def add_configuration():
    """Add a new configuration for a remote type."""
    logger.info("Adding new remote type configuration...\n")
    try:
        remote_types = get_remote_types()
        already_configured_types = sorted(load_configuration())

        while True:
            remote_type = input("Enter rclone supported remote type: ").strip()
            if remote_type not in remote_types:
                print(f"No remote is configured for '{remote_type}'.")
            elif remote_type in already_configured_types:
                if confirm(f"Edit existing configuration for {remote_type}?"):
                    edit_configuration(remote_type)
                    return
            else:
                break

            print("\nProvide the necessary flags and arguments.\n")
            remote_flags = {}
            while True:
                flag = input("Enter flag: ").strip()
                value = input("Enter value if applicable: ").strip()
                remote_flags[flag] = value
                print(f"New Configuration: {remote_type}: {remote_flags}")
                if confirm("Done?"):
                    break
            if confirm("\nSave Configuration?"):
                existing_config = load_configuration()
                existing_config[remote_type] = remote_flags
                save_configuration(existing_config)
                logger.info(f"Configuration for {remote_type} added successfully.")
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by the user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")

def edit_configuration(remote_type=None):
    """Edit an existing remote type configuration."""
    configs = load_configuration()
    if remote_type is None:
        print("Choose remote type to edit:")
        for index, remote_type in enumerate(configs, start=1):
            print(f"{index}. {remote_type}")
        remote_type = list(configs)[get_valid_index(configs) - 1]
    print(f"Current configuration for {remote_type}: {configs[remote_type]}")
    
    new_flags = {}
    while True:
        flag = input("Enter new flag: ").strip()
        value = input("Enter value if applicable: ").strip()
        new_flags[flag] = value
        configs[remote_type].update(new_flags)
        print(f"Updated Configuration for {remote_type}: {configs[remote_type]}")
        if confirm("Done?"):
            break
    if confirm("\nSave Configuration?"):
        save_configuration(configs)
        logger.info(f"Saved changes for {remote_type}.")

def delete_configuration():
    """Remove a remote type configuration."""
    configs = load_configuration()
    print("Choose remote type to delete:")
    for index, remote_type in enumerate(configs, start=1):
        print(f"{index}. {remote_type}")
    remote_type = list(configs)[get_valid_index(configs) - 1]
    if confirm(f"Delete configuration for {remote_type}?"):
        del configs[remote_type]
        save_configuration(configs)
        logger.info(f"Configuration for {remote_type} deleted successfully.")

def get_remote_types():
    """Get all remote types available in the rclone configuration."""
    remote_types = set()
    rclone_config = get_rclone_config()
    for remote in rclone_config:
        remote_types.add(rclone_config[remote]["type"])
    return sorted(remote_types)

def manage_configurations():
    """Main menu for managing flag configurations."""
    while True:
        print("\nManage remote type configurations.\n")
        for index, action in enumerate(ACTIONS, start=1):
            print(f"{index}. {list(action.keys())[0]}")

        action = list(ACTIONS[get_valid_index(ACTIONS) - 1].values())[0]
        if action is None:
            break
        action()

if __name__ == "__main__":
    try:
        manage_configurations()
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)