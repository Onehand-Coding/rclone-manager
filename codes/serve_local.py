import os
import sys
import logging
import platform
import subprocess
from pathlib import Path
from typing import List, Optional

from utils import clear_screen, choose_from_list, is_rclone_installed, get_ip_address, navigate_local_file_system
from config import configure_logging, DEFAULT_PORT, BACKENDS, USERNAME, PASSWORD

logger = logging.getLogger(__name__)


def serve_local(folder_path: str, backend: str) -> None:
    """Serves the selected folder using rclone."""
    command = [
        "rclone", "serve", backend.lower(), folder_path,
        "--addr", f"{get_ip_address()}:{DEFAULT_PORT}",
        "--user", USERNAME, "--pass", PASSWORD
    ]
    logger.debug(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error: {e}")


def main() -> None:
    """Main function to run the script."""
    configure_logging()
    is_rclone_installed()
    folder_path = navigate_local_file_system()
    backend = choose_from_list(BACKENDS, "\nChoose backend:")
    if backend:
        serve_local(folder_path, backend)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script interrupted, Bye!")
        sys.exit()