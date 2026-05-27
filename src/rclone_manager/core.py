import os
import json
import logging
import subprocess
import threading
from configparser import ConfigParser

from .config import get_project_root
from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput
from .utils import (
    _run_rclone_with_stats,
    choose_from_list,
    get_remote_type,
    get_rclone_flags,
    navigate_local_file_system,
    navigate_remote_file_system,
    list_rclone_remotes,
    sanitize_command,
)

console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()
logger = logging.getLogger(__name__)


def serve_remote():
    """
    Serves one or more remote destinations using rclone.
    Handles Google Drive shared drives specifically.
    """
    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    # Step 1: Select Remote(s)
    console.print("\n[bold cyan]-- Step 1: Select Remote(s) to Serve --[/bold cyan]")
    selected_remotes = choose_from_list(
        remotes, "Select one or more remotes to serve (e.g., 1 or 1,2):", multi=True
    )
    if not selected_remotes:
        return
    if not isinstance(selected_remotes, list):
        selected_remotes = [selected_remotes]

    # Step 2: Select Backend
    console.print("\n[bold cyan]-- Step 2: Select Backend --[/bold cyan]")
    backend = choose_from_list(["http", "webdav", "ftp"], "Select the backend to use:")
    if not backend:
        return

    # --- Separate Planning from Execution ---

    # 1. Planning Phase: Determine all jobs to run first.
    jobs_to_run = []
    port = int(os.environ.get("DEFAULT_PORT", 8080))

    for remote in selected_remotes:
        # Add the main remote job
        jobs_to_run.append({"remote": remote, "port": port, "shared": False})

        remote_type = get_remote_type(remote)
        if remote_type == "drive":
            serve_shared = console.input(
                f"[yellow]Serve shared drive for '{remote}' as well? (y/n)[/yellow]",
                choices=["y", "n"],
                default="y",
            )
            if serve_shared == "y":
                # Add the shared drive job
                jobs_to_run.append({"remote": remote, "port": port + 1, "shared": True})
                port += 2  # Increment port by 2 for the next remote
            else:
                port += 1  # Increment port by 1
        else:
            port += 1  # Increment port by 1

    # 2. Execution Phase: Start all planned jobs.
    threads = []
    username = os.environ.get("USERNAME", "user")
    password = os.environ.get("PASSWORD", "pass")

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

    # Wait for all threads to complete (i.e., until Ctrl+C is pressed)
    for thread in threads:
        thread.join()


def _serve_remote_thread(
    remote: str, backend: str, port: int, user: str, passw: str, shared: bool
):
    """
    A helper function to serve a remote in a separate thread.
    """
    remote_type = get_remote_type(remote)
    flags = get_rclone_flags(remote_type)

    remote_path = f"{remote}:"

    # For Google Drive, we need to handle the shared flag carefully.
    if remote_type == "drive":
        # If we are serving the SHARED drive...
        if shared:
            # We use the specially named remote for shared drives (e.g., Gdrive-shared:)
            # Note: rclone uses the original remote name plus the flag, not a separate remote name.
            # The remote_path for the command should still point to the original remote.
            # We just ensure the flag is present.
            if "--drive-shared-with-me" not in flags:
                flags.append("--drive-shared-with-me")
        # If we are serving the MAIN drive...
        else:
            # We must REMOVE the shared flag if it came from the config
            if "--drive-shared-with-me" in flags:
                flags.remove("--drive-shared-with-me")

    # Build the final command
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

    # Determine the display name for the log message
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
    """
    Serves a local directory using rclone.
    """
    # Step 1: Select Local Directory
    console.print("\n[bold cyan]-- Step 1: Select Local Directory --[/bold cyan]")
    local_path = navigate_local_file_system(purpose="directory")
    if not local_path:
        return

    # Step 2: Select Backend
    console.print("\n[bold cyan]-- Step 2: Select Backend --[/bold cyan]")
    backends = choose_from_list(["http", "webdav", "ftp"], "Select the backend to use:")
    if not backends:
        return
    backend = backends[0] if isinstance(backends, list) else backends

    port = os.environ.get("DEFAULT_PORT", 8080)
    bind_addr = os.environ.get("BIND_ADDRESS", "127.0.0.1")
    username = os.environ.get("USERNAME", "user")
    password = os.environ.get("PASSWORD", "pass")

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


def upload_backup(overwrite: bool = False):
    """
    Uploads files or a directory to a remote destination.
    """
    from .config import get_project_root, get_filters, build_filter_args

    console.rule("[bold]⬆️ Upload[/bold]")

    console.print(
        "\n[bold cyan]-- Step 1: Select Local Files/Folder to Upload --[/bold cyan]"
    )
    local_selection = navigate_local_file_system(purpose="file or folder")
    if not local_selection:
        return

    console.print("\n[bold cyan]-- Step 2: Select a Remote --[/bold cyan]")
    remotes = list_rclone_remotes()
    if not remotes:
        return
    remote = choose_from_list(remotes, "Select the destination remote:")
    if not remote:
        return

    console.print(
        "\n[bold cyan]-- Step 3: Select Remote Destination Folder --[/bold cyan]"
    )
    remote_dir = navigate_remote_file_system(
        remote, purpose="destination folder", single_only=True
    )
    if not remote_dir:
        return

    # Ensure the remote path is treated as a directory
    if isinstance(remote_dir, list):
        remote_dir = remote_dir[0]
    if not remote_dir.endswith("/"):
        remote_dir = remote_dir.strip("/") + "/"

    # Optional: Add temporary exclude patterns for this upload
    console.print(
        "\n[dim]Add exclude patterns for this upload? (comma-separated, or skip)[/dim]"
    )
    console.print("[dim]Examples: *.log, temp/, __pycache__/[/dim]")
    exclude_input = console.input("Exclude patterns", default="")
    temp_filters = []
    if exclude_input.strip():
        temp_filters = [p.strip() for p in exclude_input.split(",") if p.strip()]

    console.rule("[green]Starting Upload[/green]")

    # Build filter arguments: global filters + temporary upload filters
    root = get_project_root()
    global_filters = get_filters(root)
    all_exclude = global_filters["exclude"] + temp_filters
    filter_args = build_filter_args(
        {"exclude": all_exclude, "include": global_filters["include"]}
    )

    base_command = ["rclone", "copy"]
    if overwrite:
        console.print("[yellow]Overwrite mode enabled.[/yellow]")
        base_command.append("--ignore-times")

    if isinstance(local_selection, str):
        base_command.extend(filter_args)
        command = base_command + [local_selection, remote_dir]
        label = f"Uploading {os.path.basename(local_selection)}"
        returncode, errors = _run_rclone_with_stats(label, command)
    else:
        files_to_upload_list = local_selection

        base_dir = os.path.dirname(files_to_upload_list[0])
        file_names = [os.path.basename(f) for f in files_to_upload_list]

        console.print(f"Uploading {len(file_names)} files from {base_dir}...")

        command = base_command + [
            "--files-from",
            "-",
            base_dir,
            remote_dir,
        ]

        label = f"Uploading {len(file_names)} files"
        stdin_data = "\n".join(file_names)
        returncode, errors = _run_rclone_with_stats(
            label, command, stdin_data=stdin_data
        )

    if returncode == 0:
        console.rule("[bold green]✅ Upload Complete[/bold green]")
    else:
        console.print("[red]❌ Upload failed.[/red]")
        for e in errors:
            console.print(f"[red]   {e}[/red]")


def download_backup(overwrite: bool = False):
    """
    Downloads one or more files/directories from a remote destination.
    """
    from .config import get_project_root, get_filters, build_filter_args

    console.rule("[bold]⬇️ Download[/bold]")

    console.print(
        "\n[bold cyan]-- Step 1: Select a Remote to Download From --[/bold cyan]"
    )
    remotes = list_rclone_remotes()
    if not remotes:
        return
    remote = choose_from_list(remotes, "Select the source remote:")
    if not remote:
        return

    console.print(
        "\n[bold cyan]-- Step 2: Select Remote Files/Folders to Download --[/bold cyan]"
    )
    remote_selection = navigate_remote_file_system(
        remote, purpose="files/folders to download"
    )
    if not remote_selection:
        return

    console.print(
        "\n[bold cyan]-- Step 3: Select Local Destination Folder --[/bold cyan]"
    )
    local_dir = navigate_local_file_system(
        purpose="destination folder", single_only=True
    )
    if not local_dir:
        return

    if isinstance(local_dir, list):
        local_dir = local_dir[0]
    if os.path.isfile(local_dir):
        console.print("[red]Invalid destination. You must select a directory.[/red]")
        return

    # Optional: Add temporary exclude patterns for this download
    console.print(
        "\n[dim]Add exclude patterns for this download? (comma-separated, or skip)[/dim]"
    )
    console.print("[dim]Examples: *.tmp, .cache/, Thumbs.db[/dim]")
    exclude_input = console.input("Exclude patterns", default="")
    temp_filters = []
    if exclude_input.strip():
        temp_filters = [p.strip() for p in exclude_input.split(",") if p.strip()]

    console.rule("[green]Starting Download[/green]")

    # Build filter arguments: global filters + temporary download filters
    root = get_project_root()
    global_filters = get_filters(root)
    all_exclude = global_filters["exclude"] + temp_filters
    filter_args = build_filter_args(
        {"exclude": all_exclude, "include": global_filters["include"]}
    )

    base_command = ["rclone", "copy"]
    if overwrite:
        console.print("[yellow]Overwrite mode enabled (ignoring timestamps).[/yellow]")
        base_command.append("--ignore-times")

    if isinstance(remote_selection, str):
        base_command.extend(filter_args)
        console.print(
            f"Downloading {os.path.basename(remote_selection.rstrip('/'))} to {local_dir}..."
        )
        command = base_command + [remote_selection, local_dir]
        label = f"Downloading {os.path.basename(remote_selection.rstrip('/'))}"
        returncode, errors = _run_rclone_with_stats(label, command)
    else:
        files_to_download_list = remote_selection

        if overwrite:
            failed_items = []
            for item in files_to_download_list:
                console.print(f"Downloading 📄 {os.path.basename(item.rstrip('/'))}...")
                command = base_command + filter_args + [item, local_dir]
                label = f"Downloading {os.path.basename(item.rstrip('/'))}"
                rc, errs = _run_rclone_with_stats(label, command)
                if rc != 0:
                    failed_items.append((item, errs))

            if failed_items:
                console.print(f"\n[red]❌ {len(failed_items)} item(s) failed:[/red]")
                for item, errs in failed_items:
                    console.print(f"  [red]{item}[/red]")
                    for e in errs:
                        console.print(f"    [red]{e}[/red]")
            else:
                console.rule("[bold green]✅ Download Complete[/bold green]")
            return

        else:
            remote_path_base = os.path.dirname(files_to_download_list[0]) + "/"
            file_names_only = [
                os.path.basename(f.rstrip("/")) for f in files_to_download_list
            ]
            console.print(f"Downloading {len(file_names_only)} items to {local_dir}...")
            command = base_command + [
                "--files-from",
                "-",
                remote_path_base,
                local_dir,
            ]
            label = f"Downloading {len(file_names_only)} items"
            stdin_data = "\n".join(file_names_only)
            returncode, errors = _run_rclone_with_stats(
                label, command, stdin_data=stdin_data
            )

    if returncode == 0:
        console.rule("[bold green]✅ Download Complete[/bold green]")
    else:
        console.print("[red]❌ Download failed.[/red]")
        for e in errors:
            console.print(f"[red]   {e}[/red]")


def manage_config():
    """
    Provides a menu to manage rclone flags in the config.ini file.
    """
    config_path = os.path.join(get_project_root(), "configs", "config.ini")
    config = ConfigParser()
    config.read(config_path)

    if "rclone_flags" not in config:
        config["rclone_flags"] = {}

    def save_changes():
        with open(config_path, "w") as f:
            config.write(f)
        console.print("[green]Configuration saved successfully![/green]")

    while True:
        console.print("\n[bold cyan]--- Configuration Management ---[/bold cyan]")
        console.print("1. View Current Flags")
        console.print("2. Add/Edit Flag for a Remote Type")
        console.print("3. Delete Flag from a Remote Type")
        console.print(
            "4. Toggle Hidden Files (currently: {})".format(
                "included"
                if os.environ.get("INCLUDE_HIDDEN", "false").lower() == "true"
                else "excluded"
            )
        )
        console.print("5. Exit")
        choice = console.input(
            "Enter your choice", choices=["1", "2", "3", "4", "5"], default="5"
        )

        if choice == "1":
            for remote_type, flags in config["rclone_flags"].items():
                console.print(f"\n[bold]{remote_type}[/bold]:")
                # The flags are a single string, so we split it for display
                for flag in flags.splitlines():
                    if flag:
                        console.print(f"  {flag}")
            input("\nPress Enter to continue...")

        elif choice == "2":
            remote_type = console.input(
                "Enter the remote type (e.g., drive, mega)"
            ).lower()
            flag_to_add = console.input(
                "Enter the full flag to add/edit (e.g., --vfs-cache-mode=full)"
            )

            # Get existing flags or start fresh
            existing_flags = config.get(
                "rclone_flags", remote_type, fallback=""
            ).splitlines()
            # The key of the flag (e.g., --vfs-cache-mode)
            flag_key = flag_to_add.split("=")[0]

            # Remove any old version of the flag and add the new one
            new_flags = [f for f in existing_flags if not f.startswith(flag_key)]
            new_flags.append(flag_to_add)

            config["rclone_flags"][remote_type] = "\n".join(new_flags)
            save_changes()

        elif choice == "3":
            remote_type = console.input("Enter the remote type").lower()
            if not config.has_option("rclone_flags", remote_type):
                console.print(f"[red]No flags found for '{remote_type}'.[/red]")
                continue

            flag_to_delete = console.input(
                "Enter the flag key to delete (e.g., --vfs-cache-mode)"
            )
            existing_flags = config.get("rclone_flags", remote_type).splitlines()
            new_flags = [f for f in existing_flags if not f.startswith(flag_to_delete)]

            config["rclone_flags"][remote_type] = "\n".join(new_flags)
            save_changes()

        elif choice == "4":
            current = config.get("DEFAULT", "INCLUDE_HIDDEN", fallback="false")
            new_val = "true" if current.lower() == "false" else "false"
            config["DEFAULT"]["INCLUDE_HIDDEN"] = new_val
            os.environ["INCLUDE_HIDDEN"] = new_val
            save_changes()
            console.print(
                f"[green]Hidden files are now {'included' if new_val == 'true' else 'excluded'}.[/green]"
            )

        elif choice == "5":
            break


def sync_remotes(dry_run: bool = False, preview: bool = False, force: bool = False):
    """
    Syncs between two rclone remotes.

    Args:
        dry_run: Show what would change without making any changes
        preview: Run rclone check first to show diff, then confirm
        force: Skip confirmation prompt
    """
    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    source_remote = choose_from_list(remotes, "Select the source remote:")
    if not source_remote:
        return

    source_path = navigate_remote_file_system(source_remote, purpose="source path")
    if not source_path:
        return

    destination_remote = choose_from_list(remotes, "Select the destination remote:")
    if not destination_remote:
        return

    destination_path = navigate_remote_file_system(
        destination_remote, purpose="destination path"
    )
    if not destination_path:
        return

    # Show destructive warning
    console.print("\n[yellow]⚠️  DESTRUCTIVE OPERATION[/yellow]")
    console.print(f"[yellow]Source:      {source_path}[/yellow]")
    console.print(f"[yellow]Destination: {destination_path}[/yellow]")
    console.print(
        "[yellow]Files on destination not in source will be DELETED permanently.[/yellow]\n"
    )

    # If --preview, run rclone check first
    if preview:
        console.print("[bold]Running preview (rclone check)...[/bold]\n")
        try:
            # Use two-pass approach to properly categorize files
            # Files only in source (missing on dst)
            result_src = _runner.run(
                ["rclone", "check", source_path, destination_path, "--missing-on-dst"],
                capture_output=True,
                text=True,
            )

            # Files only in dest (missing on src)
            result_dst = _runner.run(
                ["rclone", "check", source_path, destination_path, "--missing-on-src"],
                capture_output=True,
                text=True,
            )

            # Files that differ (sizes/hashes differ)
            result_diff = _runner.run(
                ["rclone", "check", source_path, destination_path],
                capture_output=True,
                text=True,
            )

            # Parse stderr (rclone outputs check results to stderr)
            only_in_source = []
            only_in_dest = []
            differ = []

            # Parse files only in source
            for line in result_src.stderr.strip().split("\n"):
                if not line.strip():
                    continue
                # Format: ERROR : <path>: file not in one directory
                if "file not in one directory" in line or "file not in Remote" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        path = parts[1].strip()
                        only_in_source.append(path)

            # Parse files only in dest
            for line in result_dst.stderr.strip().split("\n"):
                if not line.strip():
                    continue
                if "file not in one directory" in line or "file not in Local" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        path = parts[1].strip()
                        only_in_dest.append(path)

            # Parse files that differ
            for line in result_diff.stderr.strip().split("\n"):
                if not line.strip():
                    continue
                if "Sizes differ" in line or "Hashes differ" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        path = parts[1].strip()
                        differ.append(path)

            if only_in_source or only_in_dest or differ:
                if only_in_source:
                    console.print(
                        f"\n[green]+ {len(only_in_source)} files only in SOURCE (will be COPIED):[/green]"
                    )
                    for f in only_in_source[:10]:
                        console.print(f"  [green]+ {f}[/green]")
                    if len(only_in_source) > 10:
                        console.print(
                            f"  [dim]... and {len(only_in_source) - 10} more[/dim]"
                        )

                if only_in_dest:
                    console.print(
                        f"\n[red]- {len(only_in_dest)} files only in DESTINATION (will be DELETED):[/red]"
                    )
                    for f in only_in_dest[:10]:
                        console.print(f"  [red]- {f}[/red]")
                    if len(only_in_dest) > 10:
                        console.print(
                            f"  [dim]... and {len(only_in_dest) - 10} more[/dim]"
                        )

                if differ:
                    console.print(
                        f"\n[yellow]~ {len(differ)} files differ (will be OVERWRITTEN):[/yellow]"
                    )
                    for f in differ[:10]:
                        console.print(f"  [yellow]~ {f}[/yellow]")
                    if len(differ) > 10:
                        console.print(f"  [dim]... and {len(differ) - 10} more[/dim]")

                console.print()
            else:
                console.print(
                    "[green]✓ No differences found. Files are identical.[/green]\n"
                )

        except Exception as e:
            console.print(f"[yellow]⚠️  Preview failed: {e}[/yellow]\n")

    # Handle confirmation based on flags
    if dry_run:
        console.print("[dim]Dry run mode: No changes will be made.[/dim]\n")
    elif not force:
        from rich.prompt import Confirm

        if not Confirm.ask("[bold red]Proceed with sync?[/bold red]", default=False):
            console.print("[dim]Sync cancelled.[/dim]")
            return

    # Build command
    command = ["rclone", "sync", source_path, destination_path]
    if dry_run:
        command.append("--dry-run")

    # Run sync
    label = "Dry run" if dry_run else "Syncing"
    returncode, errors = _run_rclone_with_stats(label, command)

    if returncode == 0:
        if dry_run:
            console.print("[green]✅ Dry run complete. No changes were made.[/green]")
        else:
            console.print("[green]✅ Sync complete.[/green]")
    else:
        console.print("[red]❌ Sync failed.[/red]")
        for e in errors:
            console.print(f"[red]   {e}[/red]")


def generate_default_config():
    """
    Generates a default config.ini file with example configuration.
    """
    config_path = os.path.join(get_project_root(), "configs", "config.ini")

    if os.path.exists(config_path):
        console.print(
            "[yellow]config.ini already exists. Remove it first to generate a new one.[/yellow]"
        )
        return

    config = ConfigParser()

    # Add DEFAULT section
    config["DEFAULT"] = {
        "LOG_LEVEL": "INFO",
        "LOG_FILE": "logs/rclone_scripts.log",
        "DEFAULT_PORT": "8080",
        "USERNAME": "your_username",
        "PASSWORD": "your_secret_password",
        "INCLUDE_HIDDEN": "false",
    }

    # Add rclone_flags section with examples
    config["rclone_flags"] = {
        "mega": "--vfs-cache-mode=full\n--vfs-cache-max-size=1G\n--vfs-cache-max-age=24h",
        "drive": "--vfs-cache-mode=full\n--vfs-cache-max-size=2G",
        "google photos": "--gphotos-read-size\n--vfs-cache-mode=full\n--vfs-cache-max-size=10G\n--vfs-cache-max-age=24h",
    }

    # Add filters section with default exclude patterns
    config["filters"] = {
        "exclude": "\n".join(
            [
                "node_modules/",
                "__pycache__/",
                "*.pyc",
                "*.tmp",
                "*.swp",
            ]
        )
    }

    with open(config_path, "w") as configfile:
        config.write(configfile)

    console.print(
        f"[green]Successfully created default config at {config_path}[/green]"
    )


def check_remote(overwrite: bool = False):
    """
    Verifies integrity of files between a local path and a remote using rclone check.
    """
    console.rule("[bold]🔍 Checksum Verify[/bold]")

    console.print("\n[bold cyan]-- Step 1: Select Local Directory --[/bold cyan]")
    local_path = navigate_local_file_system(purpose="directory")
    if not local_path:
        return

    console.print("\n[bold cyan]-- Step 2: Select Remote --[/bold cyan]")
    remotes = list_rclone_remotes()
    if not remotes:
        return
    remote = choose_from_list(remotes, "Select remote to check against:")
    if not remote:
        return

    console.print("\n[bold cyan]-- Step 3: Select Remote Path --[/bold cyan]")
    remote_path = navigate_remote_file_system(remote, purpose="remote path")
    if not remote_path:
        return

    console.rule("[green]Running Check[/green]")
    command = ["rclone", "check", local_path, remote_path]
    with console.status("[dim]Checking files...[/dim]"):
        result = _runner.run(command)

    if result.returncode == 0:
        console.print("[bold green]✅ All files match![/bold green]")
    else:
        console.print(
            "[bold yellow]⚠️ Differences found. Check output above.[/bold yellow]"
        )


def ls_remote():
    """
    Browse and list contents of a remote without mounting or serving.
    """
    console.rule("[bold]📋 List Remote[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    console.print("\n[bold cyan]-- Step 1: Select Remote to Browse --[/bold cyan]")
    remote = choose_from_list(remotes, "Select remote to browse:")
    if not remote:
        return

    from .utils import _fzf_available, _run_fzf

    current_path = f"{remote}:"
    while True:
        items = None
        dirs = []
        files = []
        use_lsf = False

        try:
            with console.status(f"[dim]Listing {current_path}...[/dim]"):
                output = _runner.check_output(
                    ["rclone", "lsjson", current_path], stderr=subprocess.PIPE
                )

            items = json.loads(output)
            dirs = [i for i in items if i["IsDir"]]
            files = [i for i in items if not i["IsDir"]]

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""

            if "invalid_grant" in stderr or "token" in stderr.lower():
                console.print(
                    f"[bold red]Authentication error for [cyan]{remote}[/cyan]. Token may be expired.[/bold red]"
                )
                console.print(f"[dim]Run: rclone config reconnect {remote}[/dim]")
                break
            elif (
                "SIGSEGV" in stderr
                or "nil pointer" in stderr
                or "mega" in stderr.lower()
            ):
                console.print(
                    f"[bold yellow]MEGA backend error for [cyan]{remote}[/cyan]. Falling back to lsf...[/bold yellow]"
                )
                use_lsf = True
            else:
                console.print(f"[bold red]Error listing path: {e}[/bold red]")
                break

        if use_lsf and items is None:
            try:
                with console.status(
                    f"[dim]Listing {current_path} with lsf fallback...[/dim]"
                ):
                    dirs_output = _runner.check_output(
                        ["rclone", "lsf", "--dirs-only", current_path]
                    )
                    files_output = _runner.check_output(
                        ["rclone", "lsf", "--files-only", current_path]
                    )

                dir_names = [
                    d.strip().rstrip("/")
                    for d in dirs_output.strip().split("\n")
                    if d.strip()
                ]
                file_names = [
                    f.strip() for f in files_output.strip().split("\n") if f.strip()
                ]

                dirs = [
                    {"Name": d, "IsDir": True, "Size": 0, "ModTime": ""}
                    for d in dir_names
                ]
                files = [
                    {"Name": f, "IsDir": False, "Size": 0, "ModTime": ""}
                    for f in file_names
                ]

            except subprocess.CalledProcessError as e2:
                stderr2 = (
                    e2.stderr.decode("utf-8", errors="replace") if e2.stderr else ""
                )
                if "invalid_grant" in stderr2 or "token" in stderr2.lower():
                    console.print(
                        f"[bold red]Authentication error for [cyan]{remote}[/cyan]. Token may be expired.[/bold red]"
                    )
                    console.print(f"[dim]Run: rclone config reconnect {remote}[/dim]")
                else:
                    console.print(f"[bold red]Error listing path: {e2}[/bold red]")
                break

        if _fzf_available():
            display_items = []
            for d in dirs:
                display_items.append(f"📁 {d['Name']}/")
            for f in files:
                size = f.get("Size", 0)
                if size >= 1_073_741_824:
                    size_str = f"{size / 1_073_741_824:.1f} GB"
                elif size >= 1_048_576:
                    size_str = f"{size / 1_048_576:.1f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
                display_items.append(
                    f"📄 {f['Name']}  {size_str}  {f.get('ModTime', '')[:10]}"
                )
            display_items.append(".. (go up)")
            display_items.append("q (quit)")

            selected = _run_fzf(display_items, prompt=f"📂 {current_path} > ")
            if not selected:
                break

            choice = selected[0]
            if choice == "q (quit)":
                break
            elif choice == ".. (go up)":
                if current_path.rstrip("/") == f"{remote}:":
                    continue
                current_path = current_path.rstrip("/")
                current_path = current_path.rsplit("/", 1)[0] + "/"
                if not current_path.endswith(":"):
                    current_path = current_path.rsplit("/", 1)[0] + "/"
            else:
                name = choice[2:].split("  ")[0].rstrip("/")
                current_path = current_path.rstrip("/") + "/" + name + "/"
        else:
            if not dirs and not files:
                console.print("[dim]-- Empty --[/dim]")

            for i, d in enumerate(dirs, 1):
                console.print(f"  {i:>3}. 📁 [bold]{d['Name']}[/bold]")

            for i, f in enumerate(files, len(dirs) + 1):
                size = f.get("Size", 0)
                date = f.get("ModTime", "")[:10]
                if size >= 1_073_741_824:
                    size_str = f"{size / 1_073_741_824:.1f} GB"
                elif size >= 1_048_576:
                    size_str = f"{size / 1_048_576:.1f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
                console.print(
                    f"  {i:>3}. 📄 {f['Name']}  [dim]{size_str}  {date}[/dim]"
                )

            choice = console.input(
                "\n[yellow]Number to enter folder, '..' to go up, 'q' to quit[/yellow]"
            )

            if choice and choice.lower() == "q":
                break
            elif choice == "..":
                if current_path.rstrip("/") == f"{remote}:":
                    continue
                current_path = os.path.dirname(current_path.rstrip("/"))
                if not current_path.endswith(":"):
                    current_path += "/"
            elif choice:
                try:
                    idx = int(choice.strip()) - 1
                    if 0 <= idx < len(dirs):
                        current_path = (
                            current_path.rstrip("/") + "/" + dirs[idx]["Name"] + "/"
                        )
                    else:
                        console.print(
                            "[bold red]Invalid choice. That's a file, not a folder.[/bold red]"
                        )
                except ValueError:
                    console.print(
                        "[bold red]Invalid choice. Please enter a number, '..', or 'q'.[/bold red]"
                    )
                    continue


def dedupe_remote():
    """
    Find and remove duplicate files on a remote using rclone dedupe.
    """
    console.rule("[bold]🗑️ Dedupe Remote[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    # Step 1: Select Remote
    console.print("\n[bold cyan]-- Step 1: Select Remote --[/bold cyan]")
    remote = choose_from_list(remotes, "Select remote to dedupe:")
    if not remote:
        return

    # Step 2: Select Remote Path
    console.print("\n[bold cyan]-- Step 2: Select Remote Path --[/bold cyan]")
    remote_path = navigate_remote_file_system(remote, purpose="remote path")
    if not remote_path:
        return

    # Step 3: Select Dedupe Mode
    console.print("\n[bold cyan]-- Step 3: Select Dedupe Mode --[/bold cyan]")
    mode = choose_from_list(
        ["interactive", "first", "newest", "oldest", "largest", "smallest", "rename"],
        "Select dedupe mode:",
    )
    if not mode:
        return

    console.print(
        f"\n[yellow]⚠️  Running dedupe in [bold]{mode}[/bold] mode on {remote_path}[/yellow]"
    )
    if mode != "interactive":
        confirm = console.input(
            "Are you sure? This may delete files. (y/n)",
            choices=["y", "n"],
            default="n",
        )
        if confirm != "y":
            console.print("[dim]Cancelled.[/dim]")
            return

    with console.status(f"[dim]Running dedupe on {remote_path}...[/dim]"):
        command = ["rclone", "dedupe", f"--dedupe-mode={mode}", remote_path]
        _runner.run(command)
    console.rule("[bold green]✅ Dedupe Complete[/bold green]")


def space_remote():
    """
    Show quota and usage for all configured remotes.
    """
    console.rule("[bold]💾 Remote Storage Usage[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    # Step 1: Select Remote(s) to Check
    console.print("\n[bold cyan]-- Step 1: Select Remote(s) to Check --[/bold cyan]")
    selected = choose_from_list(
        remotes, "Select remote(s) to check (e.g., 1 or 1,2 or 'all'):", multi=True
    )
    if not selected:
        return
    if not isinstance(selected, list):
        selected = [selected]

    for remote in selected:
        console.print(f"\n[bold cyan]── {remote} ──[/bold cyan]")
        try:
            with console.status(f"[dim]Fetching quota for {remote}...[/dim]"):
                result = _runner.run(
                    ["rclone", "about", f"{remote}:"], capture_output=True, text=True
                )
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                console.print(
                    f"[yellow]⚠️  {remote}: quota info not available ({result.stderr.strip()})[/yellow]"
                )
        except Exception as e:
            console.print(f"[red]Error checking {remote}: {e}[/red]")


def copy_between():
    """
    Copy files directly between two remotes without downloading locally.
    """
    console.rule("[bold]🔀 Copy Between Remotes[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    console.print("\n[bold cyan]-- Step 1: Select Source Remote --[/bold cyan]")
    source_remote = choose_from_list(remotes, "Select source remote:")
    if not source_remote:
        return

    console.print("\n[bold cyan]-- Step 2: Select Source Path --[/bold cyan]")
    source_path = navigate_remote_file_system(source_remote, purpose="source path")
    if not source_path:
        return

    console.print("\n[bold cyan]-- Step 3: Select Destination Remote --[/bold cyan]")
    dest_remote = choose_from_list(remotes, "Select destination remote:")
    if not dest_remote:
        return

    console.print("\n[bold cyan]-- Step 4: Select Destination Path --[/bold cyan]")
    dest_path = navigate_remote_file_system(dest_remote, purpose="destination path")
    if not dest_path:
        return

    console.rule("[green]Starting Remote-to-Remote Copy[/green]")
    console.print(f"[dim]{source_path} → {dest_path}[/dim]")

    command = ["rclone", "copy", source_path, dest_path]
    returncode, errors = _run_rclone_with_stats("Copying", command)

    if returncode == 0:
        console.rule("[bold green]✅ Copy Complete[/bold green]")
    else:
        console.print("[red]❌ Copy failed.[/red]")
        for e in errors:
            console.print(f"[red]   {e}[/red]")


def bisync_remotes():
    """
    Two-way sync between two remotes using rclone bisync.
    """
    console.rule("[bold]🔄 Bisync Remotes[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    console.print("\n[bold cyan]-- Step 1: Select First Remote --[/bold cyan]")
    remote1 = choose_from_list(remotes, "Select first remote:")
    if not remote1:
        return
    path1 = navigate_remote_file_system(remote1, purpose="first remote path")
    if not path1:
        return

    console.print("\n[bold cyan]-- Step 2: Select Second Remote --[/bold cyan]")
    remote2 = choose_from_list(remotes, "Select second remote:")
    if not remote2:
        return
    path2 = navigate_remote_file_system(remote2, purpose="second remote path")
    if not path2:
        return

    resync = console.input(
        "\n[yellow]Run with --resync? (required on first run) (y/n)[/yellow]",
        choices=["y", "n"],
        default="n",
    )

    console.rule("[green]Starting Bisync[/green]")
    console.print(f"[dim]{path1} ↔ {path2}[/dim]")

    command = ["rclone", "bisync", path1, path2]
    if resync == "y":
        command.append("--resync")

    label = "Bisync"
    returncode, errors = _run_rclone_with_stats(label, command)

    if returncode == 0:
        console.rule("[bold green]✅ Bisync Complete[/bold green]")
    else:
        console.print("[red]❌ Bisync failed.[/red]")
        for e in errors:
            console.print(f"[red]   {e}[/red]")


def manage_filters():
    """
    Interactive menu to manage global exclude/include filters.
    """
    from .config import get_filters

    root = get_project_root()
    config_path = os.path.join(root, "configs", "config.ini")

    def load_config():
        config = ConfigParser()
        config.read(config_path)
        return config

    def save_config(config):
        with open(config_path, "w") as f:
            config.write(f)

    while True:
        filters = get_filters(root)

        console.print("\n[bold cyan]--- Filter Management ---[/bold cyan]")
        console.print("\n[bold]Current Exclude Patterns:[/bold]")
        if filters["exclude"]:
            for i, pattern in enumerate(filters["exclude"], 1):
                console.print(f"  {i}. [yellow]{pattern}[/yellow]")
        else:
            console.print("  [dim]None[/dim]")

        console.print("\n[bold]Current Include Patterns:[/bold]")
        if filters["include"]:
            for i, pattern in enumerate(filters["include"], 1):
                console.print(f"  {i}. [cyan]{pattern}[/cyan]")
        else:
            console.print("  [dim]None[/dim]")

        console.print("\n1. Add Exclude Pattern")
        console.print("2. Remove Exclude Pattern")
        console.print("3. Add Include Pattern")
        console.print("4. Remove Include Pattern")
        console.print("5. Reset to Defaults")
        console.print("6. Exit")

        choice = console.input(
            "\nEnter your choice", choices=["1", "2", "3", "4", "5", "6"], default="6"
        )

        if choice == "1":
            pattern = console.input("Enter exclude pattern (e.g., *.log, node_modules/)")
            if pattern:
                config = load_config()
                if "filters" not in config:
                    config["filters"] = {}
                current = config["filters"].get("exclude", "")
                patterns = [p.strip() for p in current.split("\n") if p.strip()]
                patterns.append(pattern)
                config["filters"]["exclude"] = "\n".join(patterns)
                save_config(config)
                console.print(f"[green]✅ Added exclude pattern: {pattern}[/green]")

        elif choice == "2":
            if not filters["exclude"]:
                console.print("[yellow]No exclude patterns to remove.[/yellow]")
                continue
            selected = console.input(
                "Select pattern to remove",
                choices=[str(i) for i in range(1, len(filters["exclude"]) + 1)],
            )
            idx = int(selected) - 1
            config = load_config()
            current = config["filters"].get("exclude", "")
            patterns = [p.strip() for p in current.split("\n") if p.strip()]
            removed = patterns.pop(idx)
            config["filters"]["exclude"] = "\n".join(patterns) if patterns else ""
            save_config(config)
            console.print(f"[green]✅ Removed: {removed}[/green]")

        elif choice == "3":
            pattern = console.input("Enter include pattern (e.g., important/*, *.pdf)")
            if pattern:
                config = load_config()
                if "filters" not in config:
                    config["filters"] = {}
                current = config["filters"].get("include", "")
                patterns = [p.strip() for p in current.split("\n") if p.strip()]
                patterns.append(pattern)
                config["filters"]["include"] = "\n".join(patterns)
                save_config(config)
                console.print(f"[green]✅ Added include pattern: {pattern}[/green]")

        elif choice == "4":
            if not filters["include"]:
                console.print("[yellow]No include patterns to remove.[/yellow]")
                continue
            selected = console.input(
                "Select pattern to remove",
                choices=[str(i) for i in range(1, len(filters["include"]) + 1)],
            )
            idx = int(selected) - 1
            config = load_config()
            current = config["filters"].get("include", "")
            patterns = [p.strip() for p in current.split("\n") if p.strip()]
            removed = patterns.pop(idx)
            config["filters"]["include"] = "\n".join(patterns) if patterns else ""
            save_config(config)
            console.print(f"[green]✅ Removed: {removed}[/green]")

        elif choice == "5":
            if (
                console.input(
                    "Reset to default patterns?", choices=["y", "n"], default="n"
                )
                == "y"
            ):
                config = load_config()
                if "filters" not in config:
                    config["filters"] = {}
                defaults = [
                    "node_modules/",
                    "__pycache__/",
                    "*.pyc",
                    "*.tmp",
                    "*.swp",
                ]
                config["filters"]["exclude"] = "\n".join(defaults)
                config["filters"]["include"] = ""
                save_config(config)
                console.print("[green]✅ Reset to default patterns.[/green]")

        elif choice == "6":
            console.print("[dim]Exiting filter management.[/dim]")
            break
