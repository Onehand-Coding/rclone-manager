import json
import os
import subprocess
import sys
import logging

from .ports import CommandRunner, RealCommandRunner

logger = logging.getLogger(__name__)
_runner: CommandRunner = RealCommandRunner()


def _is_windows() -> bool:
    return sys.platform == "win32"


def _get_mount_base() -> str:
    return os.path.expanduser(
        os.environ.get("MOUNT_DIR", "~/mnt")
    )


def _registry_path() -> str:
    return os.path.join(_get_mount_base(), ".rc_ports.json")


def _load_registry() -> dict:
    try:
        with open(_registry_path()) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in registry: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load registry: {e}")
        return {}


def _rc_vfs_stats(port: int) -> dict | None:
    try:
        result = _runner.run(
            ["rclone", "rc", "vfs/stats", f"--rc-addr=127.0.0.1:{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout fetching VFS stats from port {port}")
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse VFS stats: {e}")
    except Exception as e:
        logger.warning(f"Failed to get VFS stats: {e}")
    return None
