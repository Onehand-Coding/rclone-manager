#!/usr/bin/env python3

import sys
import json
import logging
import subprocess
from pathlib import Path
from threading import Thread
from helpers import get_remote_names, choose_remote, get_remote_type, confirm

# === Configurations ===
HOME_DIR = Path(__file__).parent
DEFAULT_PORT = 8080
CONFIG_FILE =HOME_DIR / "remote-commands-config.json"


# === Logging Configuration ===
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def add_configuration():
    """Configure command/flags for a remote type."""
    logging.info("Configuring remote type flag/s...\n")
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
            logging.info(f"Remote flag/s Configuration for {remote_type} added successfully.")
    except KeyboardInterrupt:
        logging.warning(f"Remote flag Configuration aborted.")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error occured: {e}")


def load_configuration():
    """Load remote flags configurations."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            configs = json.load(f)
        return configs
    except json.JSONDecodeError:
        logging.error("Failed to load remote-flag-Configuration file.")
        sys.exit(1)


def save_configuration(Configuration):
    """Save command Configuration for each configured remote type."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(Configuration, f, indent=4)


def add_authentication(command, username, password):
    """Add authentication flags to command to add security."""
    return command + ["--user", username, "--pass", password]


def get_command(remote, remote_type, shared=False, add_auth=False, port=DEFAULT_PORT):
    """Build the rclone command based on the selected remote type."""
    if shared: port +=1
    base_command = [
        "rclone",
        "serve",
        "webdav",
        f"{remote}:",
        "--addr",
        f"localhost:{port}",
    ]

    remote_settings = load_configuration().get(remote_type)
    if remote_settings is None:
        raise ValueError(f"Unsupported remote type: {remote_type}")

    for key, value in remote_settings.items():
        if remote_type == "drive" and not shared:
            continue
        base_command.append(key)
        if value:
            base_command.append(value)

    return add_authentication(base_command, username="Admin", password="47153N") if add_auth else base_command


def run(command):
    """Execute the rclone command with error handling."""
    try:
        logging.info(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True)
    except KeyboardInterrupt:
        logging.warning("Operation canceled by the user.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error(e)
        sys.exit(1)
    except FileNotFoundError:
        logging.error("rclone is not installed or not found in your system PATH.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


def serve_gdrive(remote, authenticate):
    """Serve both personal and shared files for Google Drive using two configured remotes with thesame gdrive account."""
    shared_remote = f"{remote}-shared"
    if shared_remote not in get_remote_names():
        raise ValueError(f"No shared-remote configured for '{remote}'.")
    # Serve personal files
    personal_command = get_command(remote, remote_type="drive", shared=False, add_auth=authenticate)
    # Serve shared files on a different port
    shared_command = get_command(shared_remote, remote_type="drive", shared=True, add_auth=authenticate)

    # Run both commands in separate threads
    personal_thread = Thread(target=run, args=(personal_command,))
    shared_thread = Thread(target=run, args=(shared_command,))

    personal_thread.start()
    shared_thread.start()

    personal_thread.join()
    shared_thread.join()


def main():
    """Main function to setup remote and execute the rclone webdav commands."""
    try:
        print("Choose a remote to serve.")
        remote = choose_remote(get_remote_names())
        authenticate = confirm("Add authentication?")
        remote_type = get_remote_type(remote)
        if remote_type == "drive" and confirm("Serve shared files?"):
                serve_gdrive(remote, authenticate)
        else:
            command = get_command(remote, remote_type, add_auth=authenticate)
            run(command)
    except ValueError as ve:
        logging.error(ve)
        sys.exit(1)
    except KeyboardInterrupt:
        logging.warning("Operation canceled by the user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
