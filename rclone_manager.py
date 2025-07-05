#!/usr/bin/env python3

import os
from rclone_scripts.cli import main
from rclone_scripts.config import setup_env

if __name__ == "__main__":
    # Get the root directory of the project
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    # Setup the environment variables
    setup_env(ROOT_DIR)
    # Run the main function
    main()
