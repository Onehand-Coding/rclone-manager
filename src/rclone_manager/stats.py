import json
import subprocess
import time
import logging
from typing import Optional

from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput

logger = logging.getLogger(__name__)
console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()


def _get_rc_stats(port: int) -> Optional[dict]:
    try:
        result = _runner.run(
            ["rclone", "rc", "core/stats", f"--rc-addr=127.0.0.1:{port}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout fetching stats from port {port}")
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse stats response: {e}")
    except FileNotFoundError:
        logger.error("rclone not found")
    except Exception as e:
        logger.warning(f"Failed to get rc stats: {e}")
    return None


def _run_rclone_with_stats(
    label: str,
    command: list,
    rc_port: int = 5580,
    stdin_data: Optional[str] = None,
) -> tuple[int, list]:
    command = command + ["--rc", f"--rc-addr=127.0.0.1:{rc_port}"]

    proc = _runner.popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE if stdin_data else subprocess.DEVNULL,
        text=True,
    )

    if stdin_data and proc.stdin:
        proc.stdin.write(stdin_data)
        proc.stdin.close()

    errors = []
    with console.status("") as status:
        while proc.poll() is None:
            time.sleep(2)
            try:
                stats = _get_rc_stats(rc_port)
                if stats:
                    transferred = stats.get("bytes", 0)
                    total_bytes = stats.get("totalBytes", 0)
                    speed = stats.get("speed", 0)
                    transfers = stats.get("transfers", 0)
                    total_transfers = stats.get("totalTransfers", 0)

                    if total_bytes > 0:
                        mb_transferred = transferred / 1024 / 1024
                        mb_total = total_bytes / 1024 / 1024
                        size_str = f"{mb_transferred:.1f} MB / {mb_total:.1f} MB"
                    else:
                        mb_transferred = transferred / 1024 / 1024
                        size_str = f"{mb_transferred:.1f} MB"

                    speed_mb = speed / 1024 / 1024

                    if total_transfers > 0:
                        status.update(
                            f"[dim]{label} {transfers}/{total_transfers} files  "
                            f"{speed_mb:.1f} MB/s  {size_str}[/dim]"
                        )
                    else:
                        status.update(
                            f"[dim]{label} {speed_mb:.1f} MB/s  {size_str}[/dim]"
                        )
                else:
                    status.update(f"[dim]{label} running...[/dim]")
            except Exception as e:
                logger.warning(f"Error getting stats: {e}")
                status.update(f"[dim]{label} running...[/dim]")

    if proc.returncode != 0:
        stderr = proc.stderr.read() if proc.stderr else ""
        if stderr:
            errors = [line for line in stderr.strip().splitlines() if "ERROR" in line]
            if not errors:
                errors = stderr.strip().splitlines()[-5:]
    else:
        stderr = ""

    return proc.returncode, errors
