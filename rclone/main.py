#!/usr/bin/env python3

import sys
import logging
from logging.handlers import RotatingFileHandler
from configs import LOG_FILE
from helpers import get_valid_index, is_installed
from run_webdav import main as run_webdav
from run_backup import main as run_backup
from manage_webdav_config import manage_configurations


ACTIONS = [
    {"Run backup": lambda : run_backup()},
    {"Serve webDAV": lambda : run_webdav()},
    {"Manage webDAV configurations": lambda : manage_configurations()},
    {"Exit": lambda : sys.exit(0)}
]


def configure_logging():
    """Centralized logging configuration for consistent and unified logging."""
    log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    stream_handler = logging.StreamHandler()
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)

    logging.basicConfig(
        level=logging.DEBUG, 
        format=log_format,
        handlers=[file_handler, stream_handler]
    )


def main():
    """Run program to execute backups, serve webdav and manage configurations."""
    configure_logging()
    is_installed("rclone")
    logging.debug("Rclone scipts ready to be executed.")
    
    print("\nWhat do you want to do today master?\n")
    while True:
        print("\nChoose action:\n")
        for index, action in enumerate(ACTIONS, start=1):
            print(index, list(action.keys())[0])
        (action, command), = list(ACTIONS)[get_valid_index(ACTIONS)-1].items()
        if action == "Exit":
            logging.info("Program closed.")
        command()


if __name__ == "__main__":
    main()