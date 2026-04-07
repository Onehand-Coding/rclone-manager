import json
import logging
import os
import re
import shutil
import socket
import subprocess
import time
from typing import List, Union, Optional

from rich.console import Console
from rich.prompt import Prompt

console = Console()
logger = logging.getLogger(__name__)

_remote_list_cache = {"data": None, "timestamp": 0}
_REMOTE_CACHE_TTL = 60


def _toggle_fzf(action: str) -> None:
    """Toggle fzf on/off by writing USE_FZF to config.ini."""
    from .config import PROJECT_ROOT
    from configparser import ConfigParser

    config_path = os.path.join(PROJECT_ROOT, "configs", "config.ini")

    if not os.path.exists(config_path):
        console.print(
            "[bold red]config.ini not found. Run 'rman generate-config' first.[/bold red]"
        )
        return

    config = ConfigParser()
    config.read(config_path)

    if action == "status":
        enabled = os.environ.get("USE_FZF", "true").lower() != "false"
        has_fzf = shutil.which("fzf") is not None
        console.print("\n[bold]Fuzzy Search Status[/bold]")
        console.print(
            f"  Config  : {'[green]ON[/green]' if enabled else '[yellow]OFF[/yellow]'}"
        )
        console.print(
            f"  fzf     : {'[green]installed[/green]' if has_fzf else '[red]not found[/red]'}"
        )
        console.print(
            f"  Active  : {'[green]yes[/green]' if _fzf_available() else '[red]no[/red]'}"
        )
        return

    new_value = "true" if action == "on" else "false"

    if "DEFAULT" not in config:
        config["DEFAULT"] = {}
    config["DEFAULT"]["USE_FZF"] = new_value

    with open(config_path, "w") as f:
        config.write(f)

    label = "[green]ON[/green]" if action == "on" else "[yellow]OFF[/yellow]"
    console.print(f"\n[bold]Fuzzy search set to {label}.[/bold]")
    console.print("[dim]Restart the app for changes to take effect.[/dim]")


def _fzf_available() -> bool:
    """Check if fzf is installed and enabled in config."""
    if os.environ.get("USE_FZF", "true").lower() == "false":
        return False
    return shutil.which("fzf") is not None


def _run_fzf(items: List[str], prompt: str = "", multi: bool = False) -> List[str]:
    """Run fzf with the given items and return selected items."""
    fzf_cmd = ["fzf", "--height=40%", "--layout=reverse", "--border=rounded"]
    if prompt:
        fzf_cmd.extend(["--prompt", f"{prompt} "])
    if multi:
        fzf_cmd.append("-m")

    proc = subprocess.run(
        fzf_cmd, input="\n".join(items), capture_output=True, text=True
    )

    if proc.returncode != 0:
        return []

    return [line for line in proc.stdout.strip().split("\n") if line]


def _get_rc_stats(port: int) -> Optional[dict]:
    """
    Fetch transfer statistics from rclone's rc API.

    Args:
        port: The rc port to connect to

    Returns:
        Dict with stats (bytes, totalBytes, speed, transfers, totalTransfers) or None if unavailable
    """
    try:
        result = subprocess.run(
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
    """
    Run an rclone command with live transfer statistics display.

    Uses rclone's rc API to poll transfer stats and display:
    - Files transferred / total files
    - Bytes transferred / total bytes
    - Current transfer speed

    Args:
        label: Display label for the operation (e.g., "Syncing", "Copying")
        command: The rclone command to execute (without --rc flags)
        rc_port: Port for rclone's rc API (default: 5580)
        stdin_data: Optional data to pipe to stdin (for --files-from)

    Returns:
        Tuple of (returncode, error_messages)
    """
    command = command + ["--rc", f"--rc-addr=127.0.0.1:{rc_port}"]

    proc = subprocess.Popen(
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

    _, stderr = proc.communicate()
    if stderr:
        errors = [line for line in stderr.strip().splitlines() if "ERROR" in line]
        if not errors and proc.returncode != 0:
            errors = stderr.strip().splitlines()[-5:]

    return proc.returncode, errors


def get_ip_address() -> str:
    """
    Returns the local IP address of the machine.
    """
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


def list_rclone_remotes() -> List[str]:
    """
    Returns a list of all rclone remotes, filtering out remotes ending in '-shared'.
    Uses caching to avoid repeated subprocess calls.
    """
    global _remote_list_cache
    current_time = time.time()

    if (
        _remote_list_cache["data"] is not None
        and current_time - _remote_list_cache["timestamp"] < _REMOTE_CACHE_TTL
    ):
        return _remote_list_cache["data"]

    try:
        output = subprocess.check_output(["rclone", "listremotes"]).decode("utf-8")
        remotes = [line.strip().replace(":", "") for line in output.strip().split("\n")]
        result = [r for r in remotes if not r.endswith("-shared")]
        _remote_list_cache = {"data": result, "timestamp": current_time}
        return result
    except FileNotFoundError:
        console.print("[bold red]rclone not found. Please install it.[/bold red]")
        return []


def clear_remote_cache() -> None:
    """Clear the cached remote list."""
    global _remote_list_cache
    _remote_list_cache = {"data": None, "timestamp": 0}


def get_remote_type(remote: str) -> str:
    """
    Returns the type of a given rclone remote.
    """
    try:
        output = subprocess.check_output(
            ["rclone", "config", "show", f"{remote}:"]
        ).decode("utf-8")
        match = re.search(r"type\s*=\s*(.*)", output)
        if match:
            return match.group(1).strip().lower()
        return ""
    except subprocess.CalledProcessError:
        return ""


def get_rclone_flags(remote_type: str) -> List[str]:
    """
    Returns a list of rclone flags for a given remote type.
    """
    if not remote_type:
        return []
    flags = os.environ.get(f"RCLONE_FLAGS_{remote_type.lower().upper()}", "")
    return flags.split()


def run_rclone_with_retry(
    command: List[str],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> subprocess.CompletedProcess:
    """
    Run an rclone command with retry logic for transient failures.

    Args:
        command: The rclone command to execute
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (exponential backoff)

    Returns:
        CompletedProcess result

    Raises:
        subprocess.CalledProcessError: If all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
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


def choose_from_list(
    items: List[str],
    message: str,
    item_type: str = "items",
    allow_quit: bool = True,
    multi: bool = False,
) -> Union[List[str], str, None]:
    """
    Prompts the user to choose one or more items from a list.
    Returns a single item if one is chosen, otherwise a list.

    Args:
        items: List of items to choose from
        message: Prompt message to display
        item_type: Description of items for error messages
        allow_quit: If True, allows user to type 'q' or 'quit' to exit (returns None)
        multi: If True, allows multi-selection via fzf -m or comma-separated indices

    Returns:
        Selected item(s) or None if user quits or no items available
    """
    if not items:
        console.print(f"[bold red]No {item_type} found in this directory.[/bold red]")
        return None

    if _fzf_available():
        selected = _run_fzf(items, prompt=message, multi=multi)
        if not selected:
            console.print("[dim]Cancelled.[/dim]")
            return None
        return selected[0] if len(selected) == 1 else selected

    while True:
        for i, item in enumerate(items):
            display_item = f"{item}/" if item.endswith("/") else item
            console.print(f"{i + 1}. {display_item}")

        choices_str = Prompt.ask(f"[yellow]{message}[/yellow]")

        if allow_quit and choices_str and choices_str.lower() in ["q", "quit"]:
            console.print("[dim]Cancelled.[/dim]")
            return None

        if not choices_str:
            console.print("[bold red]Please enter a number or 'q' to quit.[/bold red]")
            continue

        if any(not i.strip().isdigit() for i in choices_str.split(",")):
            console.print(
                "[bold red]Invalid choice. Please enter numbers only (e.g., 1 or 1,2).[/bold red]"
            )
            continue

        selected_indices = [int(i.strip()) - 1 for i in choices_str.split(",")]
        if any(i < 0 or i >= len(items) for i in selected_indices):
            console.print(
                f"[bold red]Invalid choice. Please enter numbers between 1 and {len(items)}.[/bold red]"
            )
            continue

        selected_items = [items[i] for i in selected_indices]
        return selected_items[0] if len(selected_items) == 1 else selected_items


def navigate_local_file_system(purpose: str = None) -> Union[List[str], str, None]:
    """
    Allows the user to navigate the local file system and select files or a directory.

    Args:
        purpose: Optional description of what is being selected (e.g., "local folder", "source directory")
    """
    current_dir = os.path.expanduser("~")
    while True:
        try:
            all_items = sorted(
                [item for item in os.listdir(current_dir) if not item.startswith(".")]
            )

            dirs = [d for d in all_items if os.path.isdir(os.path.join(current_dir, d))]
            files = [
                f for f in all_items if os.path.isfile(os.path.join(current_dir, f))
            ]

            items = dirs + files

            if _fzf_available():
                display_items = []
                for item in items:
                    if item in dirs:
                        display_items.append(f"📁 {item}/")
                    else:
                        display_items.append(f"📄 {item}")
                display_items.append(".. (go up)")
                display_items.append(f". (select this {purpose or 'directory'})")

                selected = _run_fzf(display_items, prompt=f"📂 {current_dir} > ")
                if not selected:
                    console.print("[dim]Cancelled.[/dim]")
                    return None

                choice = selected[0]
                if choice == ".. (go up)":
                    current_dir = os.path.dirname(current_dir)
                    continue
                elif choice.startswith(". (select this"):
                    return current_dir
                else:
                    name = choice[2:].rstrip("/")
                    if name in dirs:
                        current_dir = os.path.join(current_dir, name)
                    else:
                        return os.path.join(current_dir, name)
            else:
                console.print(
                    f"\n[bold cyan]Current Directory:[/bold cyan] {current_dir}"
                )

                for i, item in enumerate(items):
                    if item in dirs:
                        console.print(f"{i + 1}. 📁 {item}/")
                    else:
                        console.print(f"{i + 1}. 📄 {item}")

                if purpose:
                    prompt = f"[yellow]Navigate by number, '..' (up), or select items (e.g., 1 or 2,3). Press '.' or 'd' to select this {purpose}, 'q' to quit.[/yellow]"
                else:
                    prompt = "[yellow]Navigate by number, '..' (up), or select items (e.g., 1 or 2,3). Press '.' or 'd' to select this directory, 'q' to quit.[/yellow]"
                choice = Prompt.ask(prompt)

                if choice and choice.lower() in ["q", "quit"]:
                    console.print("[dim]Cancelled.[/dim]")
                    return None

                if choice == "..":
                    current_dir = os.path.dirname(current_dir)
                    continue

                elif choice.lower() in [".", "d"]:
                    return current_dir

                selected_indices = [int(i.strip()) - 1 for i in choice.split(",")]
                selected_items = [items[i] for i in selected_indices]

                if len(selected_items) == 1 and selected_items[0] in dirs:
                    current_dir = os.path.join(current_dir, selected_items[0])
                else:
                    full_paths = [
                        os.path.join(current_dir, item) for item in selected_items
                    ]
                    return full_paths[0] if len(full_paths) == 1 else full_paths

        except (ValueError, IndexError):
            console.print("[bold red]Invalid choice.[/bold red]")
        except FileNotFoundError:
            console.print("[bold red]Directory not found.[/bold red]")
            current_dir = os.path.expanduser("~")


def navigate_remote_file_system(
    remote: str, purpose: str = None
) -> Union[List[str], str, None]:
    """
    Allows the user to navigate a remote file system and select one or more files/directories.

    Args:
        remote: The remote name to navigate
        purpose: Optional description of what is being selected (e.g., "destination path", "source files")
    """
    current_path = f"{remote}:"
    while True:
        try:
            with console.status("[dim]Loading...[/dim]"):
                output = subprocess.check_output(
                    ["rclone", "lsf", current_path]
                ).decode("utf-8")
            items = sorted(output.strip().split("\n")) if output.strip() else []

            if _fzf_available():
                display_items = []
                for item in items:
                    if item.endswith("/"):
                        display_items.append(f"📁 {item}")
                    else:
                        display_items.append(f"📄 {item}")
                display_items.append(".. (go up)")
                display_items.append(f". (select this {purpose or 'path'})")

                selected = _run_fzf(display_items, prompt=f"📂 {current_path} > ")
                if not selected:
                    console.print("[dim]Cancelled.[/dim]")
                    return None

                choice = selected[0]
                if choice == ".. (go up)":
                    if current_path.rstrip("/") == f"{remote}:":
                        continue
                    current_path = current_path.rstrip("/")
                    current_path = current_path.rsplit("/", 1)[0] + "/"
                    if not current_path.endswith(":"):
                        current_path = current_path.rsplit("/", 1)[0] + "/"
                elif choice.startswith(". (select this"):
                    return current_path
                else:
                    name = choice[2:]
                    if name.endswith("/"):
                        current_path = current_path.rstrip("/") + "/" + name
                    else:
                        return current_path.rstrip("/") + "/" + name
            else:
                console.print(
                    f"\n[bold cyan]Current Remote Path:[/bold cyan] {current_path}"
                )

                if not any(items):
                    console.print("[dim]-- Empty --[/dim]")

                for i, item in enumerate(items):
                    if item.endswith("/"):
                        console.print(f"{i + 1}. 📁 {item}")
                    else:
                        console.print(f"{i + 1}. 📄 {item}")

                if purpose:
                    prompt = f"[yellow]Navigate (number), go up (..), or select items (e.g., 1,2). Press '.' or 'd' to select this {purpose}, 'q' to quit.[/yellow]"
                else:
                    prompt = "[yellow]Navigate (number), go up (..), or select items (e.g., 1,2). Press '.' or 'd' to select this path, 'q' to quit.[/yellow]"
                choice = Prompt.ask(prompt)

                if choice and choice.lower() in ["q", "quit"]:
                    console.print("[dim]Cancelled.[/dim]")
                    return None

                if choice.lower() in [".", "d"]:
                    return current_path
                elif choice == "..":
                    if current_path.strip("/") == f"{remote}:".strip("/"):
                        continue
                    current_path = os.path.dirname(current_path.rstrip("/")) + "/"
                else:
                    selected_indices = [int(i.strip()) - 1 for i in choice.split(",")]
                    selected_items = [items[i] for i in selected_indices]

                    if len(selected_items) == 1 and selected_items[0].endswith("/"):
                        current_path += selected_items[0]
                    else:
                        full_paths = [current_path + item for item in selected_items]
                        return full_paths[0] if len(full_paths) == 1 else full_paths

        except (ValueError, IndexError):
            console.print("[bold red]Invalid choice.[/bold red]")
        except subprocess.CalledProcessError:
            console.print("[bold red]Error listing remote directory.[/bold red]")
            return current_path
