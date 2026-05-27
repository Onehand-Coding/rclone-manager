import os
import re
import subprocess
import time
import logging
from typing import List

from .ports import CommandRunner, RealCommandRunner, RichOutput, OutputPort

logger = logging.getLogger(__name__)
_runner: CommandRunner = RealCommandRunner()
console: OutputPort = RichOutput()

_remote_list_cache = {"data": None, "timestamp": 0}
_REMOTE_CACHE_TTL = 60


def list_rclone_remotes() -> List[str]:
    global _remote_list_cache
    current_time = time.time()

    if (
        _remote_list_cache["data"] is not None
        and current_time - _remote_list_cache["timestamp"] < _REMOTE_CACHE_TTL
    ):
        return _remote_list_cache["data"]

    try:
        output = _runner.check_output(["rclone", "listremotes"])
        remotes = [line.strip().replace(":", "") for line in output.strip().split("\n")]
        result = [r for r in remotes if not r.endswith("-shared")]
        _remote_list_cache = {"data": result, "timestamp": current_time}
        return result
    except FileNotFoundError:
        console.print("[bold red]rclone not found. Please install it.[/bold red]")
        return []


def clear_remote_cache() -> None:
    global _remote_list_cache
    _remote_list_cache = {"data": None, "timestamp": 0}


def get_remote_type(remote: str) -> str:
    try:
        output = _runner.check_output(
            ["rclone", "config", "show", f"{remote}:"]
        )
        match = re.search(r"type\s*=\s*(.*)", output)
        if match:
            return match.group(1).strip().lower()
        return ""
    except subprocess.CalledProcessError:
        return ""


def get_rclone_flags(remote_type: str) -> List[str]:
    if not remote_type:
        return []
    flags = os.environ.get(f"RCLONE_FLAGS_{remote_type.lower().upper()}", "")
    return flags.split()
