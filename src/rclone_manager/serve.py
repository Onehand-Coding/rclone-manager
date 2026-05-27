import os
import logging
import subprocess
import threading

from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput
from .navigation import choose_from_list, navigate_local_file_system
from .remote_info import get_remote_type, get_rclone_flags, list_rclone_remotes
from .utils import sanitize_command

console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()
logger = logging.getLogger(__name__)


def serve_remote():
    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    console.print("\n[bold cyan]-- Step 1: Select Remote(s) to Serve --[/bold cyan]")
    selected_remotes = choose_from_list(
        remotes, "Select one or more remotes to serve (e.g., 1 or 1,2):", multi=True
    )
    if not selected_remotes:
        return
    if not isinstance(selected_remotes, list):
        selected_remotes = [selected_remotes]

    console.print("\n[bold cyan]-- Step 2: Select Backend --[/bold cyan]")
    backend = choose_from_list(["http", "webdav", "ftp"], "Select the backend to use:")
    if not backend:
        return

    jobs_to_run = []
    port = int(os.environ.get("DEFAULT_PORT", 8080))

    for remote in selected_remotes:
        jobs_to_run.append({"remote": remote, "port": port, "shared": False})

        remote_type = get_remote_type(remote)
        if remote_type == "drive":
            serve_shared = console.input(
                f"[yellow]Serve shared drive for '{remote}' as well? (y/n)[/yellow]",
                choices=["y", "n"],
                default="y",
            )
            if serve_shared == "y":
                jobs_to_run.append({"remote": remote, "port": port + 1, "shared": True})
                port += 2
            else:
                port += 1
        else:
            port += 1

    threads = []
    username = os.environ.get("USERNAME", "user")
    password = os.environ.get("PASSWORD")
    if not password:
        console.print("[red]PASSWORD not set in environment or config. [/red]")
        console.print("[yellow]Set it in configs/config.ini under [DEFAULT]:[/yellow]")
        console.print("  PASSWORD = your_secret_password")
        return

    for job in jobs_to_run:
        thread = threading.Thread(
            target=_serve_remote_thread,
            args=(
                job["remote"],
                backend,
                job["port"],
                username,
                password,
                job["shared"],
            ),
            daemon=True,
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


def _serve_remote_thread(
    remote: str, backend: str, port: int, user: str, passw: str, shared: bool
):
    remote_type = get_remote_type(remote)
    flags = get_rclone_flags(remote_type)

    remote_path = f"{remote}:"

    if remote_type == "drive":
        if shared:
            if "--drive-shared-with-me" not in flags:
                flags.append("--drive-shared-with-me")
        else:
            if "--drive-shared-with-me" in flags:
                flags.remove("--drive-shared-with-me")

    bind_addr = os.environ.get("BIND_ADDRESS", "127.0.0.1")
    serve_env = os.environ.copy()
    serve_env["RCLONE_USER"] = user
    serve_env["RCLONE_PASS"] = passw

    command = [
        "rclone",
        "serve",
        backend,
        remote_path,
        "--addr",
        f"{bind_addr}:{port}",
    ] + flags

    display_name = f"{remote} (Shared)" if shared and remote_type == "drive" else remote

    console.print(
        f"[green]Starting server for [bold]{display_name}[/bold] on http://{bind_addr}:{port}[/green]"
    )
    safe_cmd = sanitize_command(command)
    console.print(f"[dim]Command: {' '.join(safe_cmd)}[/dim]")

    with console.status(f"[dim]Serving {display_name}...[/dim]"):
        try:
            _runner.run(command, check=True, env=serve_env)
        except subprocess.CalledProcessError as e:
            stderr = (
                e.stderr
                if isinstance(e.stderr, str)
                else e.stderr.decode("utf-8", errors="replace")
            )
            console.print(f"[bold red]Error serving {remote_path}: {stderr}[/bold red]")
            logger.error(f"Failed to serve {remote_path}: {e}")


def serve_local():
    console.print("\n[bold cyan]-- Step 1: Select Local Directory --[/bold cyan]")
    local_path = navigate_local_file_system(purpose="directory")
    if not local_path:
        return

    console.print("\n[bold cyan]-- Step 2: Select Backend --[/bold cyan]")
    backends = choose_from_list(["http", "webdav", "ftp"], "Select the backend to use:")
    if not backends:
        return
    backend = backends[0] if isinstance(backends, list) else backends

    port = os.environ.get("DEFAULT_PORT", 8080)
    bind_addr = os.environ.get("BIND_ADDRESS", "127.0.0.1")
    username = os.environ.get("USERNAME", "user")
    password = os.environ.get("PASSWORD")
    if not password:
        console.print("[red]PASSWORD not set in environment or config. [/red]")
        console.print("[yellow]Set it in configs/config.ini under [DEFAULT]:[/yellow]")
        console.print("  PASSWORD = your_secret_password")
        return

    console.print(
        f"[green]Serving {local_path} on http://{bind_addr}:{port} using {backend}...[/green]"
    )

    serve_env = os.environ.copy()
    serve_env["RCLONE_USER"] = username
    serve_env["RCLONE_PASS"] = password

    command = [
        "rclone",
        "serve",
        backend,
        "--addr",
        f"{bind_addr}:{port}",
        local_path,
    ]

    safe_cmd = sanitize_command(command)
    console.print(f"[dim]Command: {' '.join(safe_cmd)}[/dim]")
    with console.status(f"[dim]Serving {local_path}...[/dim]"):
        try:
            _runner.run(command, check=True, env=serve_env)
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Error serving {local_path}: {e}[/bold red]")
            logger.error(f"Failed to serve local path {local_path}: {e}")
