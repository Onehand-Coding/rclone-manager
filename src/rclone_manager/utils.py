import logging
import socket
import subprocess
import time
from typing import List

from .ports import CommandResult, CommandRunner, RealCommandRunner

logger = logging.getLogger(__name__)
_runner: CommandRunner = RealCommandRunner()


def sanitize_command(cmd: list) -> list:
    safe = []
    for arg in cmd:
        lower = arg.lower()
        if any(s in lower for s in ("pass", "token", "secret", "key", "auth")):
            if "=" in arg:
                key, _ = arg.split("=", 1)
                safe.append(f"{key}=***REDACTED***")
            else:
                safe.append("***REDACTED***")
        else:
            safe.append(arg)
    return safe


def get_ip_address() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except OSError as e:
        logger.warning(f"Failed to get IP address: {e}")
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP


def run_rclone_with_retry(
    command: List[str],
    max_retries: int = 3,
    base_delay: float = 1.0,
    ) -> CommandResult:
    last_exception = None

    for attempt in range(max_retries):
        try:
            result = _runner.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                return result

            error_msg = result.stderr.lower()
            retryable_errors = [
                "connection reset",
                "connection refused",
                "timeout",
                "temporary failure",
                "network",
                "i/o timeout",
            ]

            if any(err in error_msg for err in retryable_errors):
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"Transient error, retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    continue

            return result

        except subprocess.TimeoutExpired as e:
            last_exception = e
            logger.warning(f"Command timeout (attempt {attempt + 1}/{max_retries})")
        except OSError as e:
            last_exception = e
            logger.warning(f"OS error: {e} (attempt {attempt + 1}/{max_retries})")

        if attempt < max_retries - 1:
            delay = base_delay * (2**attempt)
            time.sleep(delay)

    raise subprocess.CalledProcessError(1, command, stderr=str(last_exception))
