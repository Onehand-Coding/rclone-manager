import json
from pathlib import Path
from typing import Dict, Any, Optional

from utils import clear_screen, choose_from_list
from config import CONFIG_FILE, DEFAULT_CONFIG

def load_config() -> Dict[str, Any]:
    """Loads the configuration from the config file."""
    if not CONFIG_FILE.exists():
        print("Config file not found. Creating a default one.")
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config: Dict[str, Any]) -> None:
    """Saves the configuration to the config file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    print("Configuration saved successfully!")

def view_config(config: Dict[str, Any]) -> None:
    """Displays the current configuration."""
    clear_screen()
    print("Current Configuration:")
    print(json.dumps(config, indent=4))
    input("\nPress Enter to continue...")

def add_remote_type(config: Dict[str, Any]) -> None:
    """Adds a new remote type to the configuration."""
    clear_screen()
    remote_type = input("Enter the name of the new remote type: ").strip()
    if not remote_type:
        print("Invalid remote type name.")
        return

    if remote_type in config["flags"]:
        print(f"Remote type '{remote_type}' already exists.")
        return

    config["flags"][remote_type] = {}
    print(f"Remote type '{remote_type}' added successfully.")
    save_config(config)

def delete_remote_type(config: Dict[str, Any]) -> None:
    """Deletes a remote type from the configuration."""
    clear_screen()
    remote_types = list(config["flags"].keys())
    if not remote_types:
        print("No remote types available to delete.")
        return

    remote_type = choose_from_list(remote_types, "Select a remote type to delete:")
    if not remote_type:
        return

    del config["flags"][remote_type]
    print(f"Remote type '{remote_type}' deleted successfully.")
    save_config(config)

def add_flag(config: Dict[str, Any]) -> None:
    """Adds a new flag to a remote type."""
    clear_screen()
    remote_types = list(config["flags"].keys())
    if not remote_types:
        print("No remote types available to add flags to.")
        return

    remote_type = choose_from_list(remote_types, "Select a remote type to add a flag:")
    if not remote_type:
        return

    flag = input("Enter the flag (e.g., '--vfs-cache-mode'): ").strip()
    value = input("Enter the value for the flag (leave empty if no value): ").strip()

    if not flag:
        print("Invalid flag.")
        return

    config["flags"][remote_type][flag] = value
    print(f"Flag '{flag}' added to remote type '{remote_type}' successfully.")
    save_config(config)

def edit_flag(config: Dict[str, Any]) -> None:
    """Edits an existing flag for a remote type."""
    clear_screen()
    remote_types = list(config["flags"].keys())
    if not remote_types:
        print("No remote types available to edit flags for.")
        return

    remote_type = choose_from_list(remote_types, "Select a remote type to edit a flag:")
    if not remote_type:
        return

    flags = list(config["flags"][remote_type].keys())
    if not flags:
        print(f"No flags available for remote type '{remote_type}'.")
        return

    flag = choose_from_list(flags, "Select a flag to edit:")
    if not flag:
        return

    new_value = input(f"Enter the new value for '{flag}' (leave empty to remove the value): ").strip()
    config["flags"][remote_type][flag] = new_value
    print(f"Flag '{flag}' updated successfully.")
    save_config(config)

def delete_flag(config: Dict[str, Any]) -> None:
    """Deletes a flag from a remote type."""
    clear_screen()
    remote_types = list(config["flags"].keys())
    if not remote_types:
        print("No remote types available to delete flags from.")
        return

    remote_type = choose_from_list(remote_types, "Select a remote type to delete a flag:")
    if not remote_type:
        return

    flags = list(config["flags"][remote_type].keys())
    if not flags:
        print(f"No flags available for remote type '{remote_type}'.")
        return

    flag = choose_from_list(flags, "Select a flag to delete:")
    if not flag:
        return

    del config["flags"][remote_type][flag]
    print(f"Flag '{flag}' deleted successfully.")
    save_config(config)

def main() -> None:
    """Main function to run the script."""
    config = load_config()

    while True:
        clear_screen()
        print("Configuration Management Tool")
        print("1. View Configuration")
        print("2. Add Remote Type")
        print("3. Delete Remote Type")
        print("4. Add Flag")
        print("5. Edit Flag")
        print("6. Delete Flag")
        print("7. Exit")
        choice = input("Enter your choice: ").strip()

        if choice == '1':
            view_config(config)
        elif choice == '2':
            add_remote_type(config)
        elif choice == '3':
            delete_remote_type(config)
        elif choice == '4':
            add_flag(config)
        elif choice == '5':
            edit_flag(config)
        elif choice == '6':
            delete_flag(config)
        elif choice == '7':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()