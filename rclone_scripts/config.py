import os
import logging
from logging.handlers import RotatingFileHandler
from configparser import ConfigParser
from rich.logging import RichHandler


def setup_env(root_dir: str):
    """
    Sets up the environment variables from the config.ini file.
    """
    config = ConfigParser()
    config_path = os.path.join(root_dir, "config.ini")

    if not os.path.exists(config_path):
        return

    config.read(config_path)

    # Process the [DEFAULT] section explicitly, as it's not in config.sections()
    if 'DEFAULT' in config:
        for key, value in config['DEFAULT'].items():
            os.environ[key.upper()] = value

    # Process all other named sections like [rclone_flags]
    for section_name in config.sections():
        # Get the items specifically from this section
        section_items = config.items(section_name)
        for key, value in section_items:
             # Create an environment variable like RCLONE_FLAGS_MEGA
            os.environ[f"{section_name.upper()}_{key.upper()}"] = value


def setup_logging():
    """
    Sets up logging for the application.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    log_file = os.environ.get("LOG_FILE", "logs/rclone_scripts.log")

    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Set up logging
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5),
            RichHandler(),
        ],
    )
