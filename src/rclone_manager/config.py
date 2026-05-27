import os
import logging
from typing import Optional
from pathlib import Path
from rich.logging import RichHandler
from configparser import ConfigParser
from logging.handlers import RotatingFileHandler


def find_project_root(marker: str = "pyproject.toml") -> Path:
    """Dynamically finds the project root by searching upwards for a marker file."""
    current_path = Path(__file__).resolve()
    while current_path != current_path.parent:
        if (current_path / marker).exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError(f"Project root marker '{marker}' not found.")


def get_project_root() -> Path:
    try:
        return find_project_root()
    except FileNotFoundError as e:
        raise FileNotFoundError(str(e)) from e


DEFAULTS = {
    "LOG_LEVEL": "INFO",
    "LOG_FILE": "logs/rclone_scripts.log",
    "DEFAULT_PORT": "8080",
    "INCLUDE_HIDDEN": "false",
    "USE_FZF": "true",
    "BIND_ADDRESS": "127.0.0.1",
}


def setup_env(root_dir: str):
    """
    Sets up the environment variables from the config.ini file.
    """
    config = ConfigParser()
    config_path = os.path.join(root_dir, "configs", "config.ini")

    if not os.path.exists(config_path):
        for key, value in DEFAULTS.items():
            os.environ.setdefault(key, value)
        return

    config.read(config_path)

    # Process the [DEFAULT] section explicitly, as it's not in config.sections()
    if "DEFAULT" in config:
        for key, value in config["DEFAULT"].items():
            env_key = f"RMAN_{key.upper()}"
            os.environ[env_key] = value
            if key.upper() in DEFAULTS:
                os.environ[key.upper()] = value

    # Process all other named sections like [rclone_flags]
    for section_name in config.sections():
        section_items = config.items(section_name)
        for key, value in section_items:
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


def get_filters(root_dir: Optional[str] = None) -> dict:
    """
    Load exclude/include filters from config.ini.

    Returns a dict with 'exclude' and 'include' lists of patterns.
    """
    if root_dir is None:
        try:
            root_dir = get_project_root()
        except FileNotFoundError:
            return {"exclude": [], "include": []}

    config_path = os.path.join(root_dir, "configs", "config.ini")
    filters = {"exclude": [], "include": []}

    if not os.path.exists(config_path):
        return filters

    config = ConfigParser()
    config.read(config_path)

    if "filters" not in config:
        return filters

    # Parse exclude patterns
    if "exclude" in config["filters"]:
        exclude_str = config["filters"]["exclude"]
        # Split by newlines and clean up each pattern
        patterns = [p.strip() for p in exclude_str.strip().split("\n") if p.strip()]
        filters["exclude"] = patterns

    # Parse include patterns
    if "include" in config["filters"]:
        include_str = config["filters"]["include"]
        patterns = [p.strip() for p in include_str.strip().split("\n") if p.strip()]
        filters["include"] = patterns

    return filters


def build_filter_args(filters: dict) -> list:
    """
    Convert filter dict to rclone command-line arguments.

    Auto-excludes hidden files and directories unless INCLUDE_HIDDEN=true.
    Hidden exclusion is applied first so user filters can override with --include.
    """
    args = []
    # Auto-exclude hidden files and dirs unless INCLUDE_HIDDEN=true
    if os.environ.get("INCLUDE_HIDDEN", "false").lower() != "true":
        args.extend(["--exclude", ".*", "--exclude", ".*/"])
    for pattern in filters.get("exclude", []):
        args.extend(["--exclude", pattern])
    for pattern in filters.get("include", []):
        args.extend(["--include", pattern])
    return args
