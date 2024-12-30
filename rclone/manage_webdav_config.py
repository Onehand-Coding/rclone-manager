#!/usr/bin/env python3

import sys
import json
import logging
import subprocess
from pathlib import Path
from pprint import pprint
from configs import CONFIG_FILE
from helpers import confirm, get_valid_index, get_rclone_config

# ===configurations=== #
logger = logging.getLogger(__name__)
ACTIONS = [
    {"Add New Configuration": lambda : add_configuration()}, {"View Existing Configurations": lambda : display_configuration()},
    {"Delete Configuration": lambda : delete_configuration()},
    {"Back to Main Menu": None},
]


def get_remote_types():
    """Get remote typrs based on configured remotes in rclone config file."""
    remote_types = set()
    remote_config = get_rclone_config()
    for remote in remote_config:
        remote_types.add(remote_config[remote]["type"])
    return sorted(remote_types)

def load_configuration():
    """Load remote configurations."""
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


def save_configuration(configs):
    """Save configuration for each configured remote type."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(configs, f, indent=4)


def display_configuration():
    """Display currently configured remote type."""
    configs = load_configuration()
    logging.info("Current remote type flag configurations:")
    print()
    pprint(configs)

def add_configuration():
    """Configure command/flags for a remote type and save it to configuration file."""
    logger.info("Adding new remote type configuration...\n")
    try:
        remote_types = get_remote_types()
        already_configured_types = sorted(load_configuration())
        while True:
            remote_type= ""
            while True:
                print("Enter rclone supported remote type.")
                remote_type = input("> ")
                #if remote_type not in remote_types:
                    #print(f"No remote is configured for {remote_type}.")
                if remote_type in already_configured_types:
                    if confirm(f"Edit existing configuration for {remote_type}?"):
                        edit_configuration(remote_type)
                else:
                    break
            
            print("\nProvide the necessary flags and arguments.\n")
    
            remote_flags = {}
            flag = input("Enter flag: ").strip()
            value = input("Enter value if applicable: ").strip()
            remote_flags[flag]=value
            print(f"""New Configuration:
                {remote_type}: {remote_flags}""")
            if confirm("Done?"):
                break
        
            if confirm("\nSave Configuration?"):
                existing_config = load_configuration()
                existing_config[remote_type] = remote_flags
                save_configuration(existing_config)
                logger.info(f"Configuration for {remote_type} added successfully.")
    except KeyboardInterrupt:
        logger.warning(f"Operation cancelled by the user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error occured: {e}")


def edit_configuration(remote_type=None):
    """Edit existing remote type configuration."""


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
        print("\nManage remote type configurations.\n")
        for index, action in enumerate(ACTIONS, start=1):
            print(index, list(action.keys())[0])

        command = list(ACTIONS[get_valid_index(ACTIONS)-1].values())[0]
        if command is None:
            break
        command()


if __name__ == "__main__":
    try:
        print(list(load_configuration()))
        manage_configurations()
    except KeyboardInterrupt:
        print("Operation cancelled.")
        sys.exit(0)