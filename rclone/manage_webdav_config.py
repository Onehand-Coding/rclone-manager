#!/usr/bin/env python3

import sys
import json
import logging
import subprocess
from pathlib import Path
from pprint import pprint
from configs import CONFIG_FILE
from helpers import confirm, get_valid_index

logger = logging.getLogger(__name__)
ACTIONS = {
    "1": "Add New Configuration",
    "2": "View Existing Configurations",
    "3": "Delete Configuration",
    "4": "Back to Main Menu"
}


def add_configuration():
    """Configure command/flags for a remote type and save it to configuration file."""
    logger.info("Adding remote type configuration...\n")
    try:
        remote_type= ""
        while not remote_type:
            remote_type = input("Enter remote type: ")
        
        print("\nProvide the necessary flags and arguments.\n")

        remote_flags = {}
        while True:
            flag = input("Enter flag: ").strip()
            value = input("Enter value if applicable: ").strip()
            remote_flags[flag]=value
            print(f"""New Configuration:
                {remote_type}: {remote_flags}""")
            if confirm("Done?"):
                break
        
        if confirm("\nSave Configurations?"):
            existing_config = load_configuration()
            existing_config[remote_type] = remote_flags
            save_configuration(existing_config)
            logger.info(f"Configuration for {remote_type} added successfully.")
    except KeyboardInterrupt:
        logger.warning(f"Remote flag Configuration aborted.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error occured: {e}")


def load_configuration():
    """Load remote flags configurations."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            configs = json.load(f)
        return configs
    except json.JSONDecodeError:
        logger.error("Failed to load remote-flag-Configuration file.")
        sys.exit(1)
    except FileNotFoundError:
        logger.error("Configuration file not found.")
        sys.exit(1)


def save_configuration(Configuration):
    """Save configuration for each configured remote type."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(Configuration, f, indent=4)


def delete_configuration():
    """Remove remote type fags configuration."""
    configs = load_configuration()
    print("Choose remote type to remove:")
    for index, remote_type in enumerate(configs, start=1):
        print(index, remote_type)
    remote_type = list(configs)[get_valid_index(configs) -1]
    if confirm(f"Delete configuration for {remote_type}?"):
        del configs[remote_type]
        save_configuration(configs)
        logger.info(f"Configuration for {remote_type} deleted successfully.")


def manage_configurations():
    """Menu to manage flag configurations for different remote types."""
    while True:
        print("\nManage remote flags configuration for remote types \n")
        for index, action in ACTIONS.items():
            print(index, action)

        action = get_valid_index(list(ACTIONS))
        match action:
            case 1:
                add_configuration()
            case 2:
                configs = load_configuration()
                logging.info("Current remote type flag configurations:")
                pprint(configs)
            case 3:
                delete_configuration()
            case 4:
                break


if __name__ == "__main__":
    try:
        manage_configurations()
    except KeyboardInterrupt:
        print("Operation cancelled.")
        sys.exit(0)