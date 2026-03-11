import os
import subprocess
import threading
from configparser import ConfigParser

from rich.prompt import Prompt
from rich.console import Console

from .config import PROJECT_ROOT
from .utils import (
    choose_from_list,
    get_ip_address,
    get_remote_type,
    get_rclone_flags,
    navigate_local_file_system,
    navigate_remote_file_system,
    list_rclone_remotes,
)

console = Console()


def serve_remote():
    """
    Serves one or more remote destinations using rclone.
    Handles Google Drive shared drives specifically.
    """
    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    selected_remotes = choose_from_list(
        remotes, "Select one or more remotes to serve (e.g., 1 or 1,2):"
    )
    if not selected_remotes:
        return
    if not isinstance(selected_remotes, list):
        selected_remotes = [selected_remotes]

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
            serve_shared = Prompt.ask(
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

    ip_address = get_ip_address()

    # Build the final command
    command = [
        "rclone",
        "serve",
        backend,
        remote_path,
        "--addr",
        f"{ip_address}:{port}",
        "--user",
        user,
        "--pass",
        passw,
    ] + flags

    # Determine the display name for the log message
    display_name = f"{remote} (Shared)" if shared and remote_type == "drive" else remote

    console.print(
        f"[green]Starting server for [bold]{display_name}[/bold] on http://{ip_address}:{port}[/green]"
    )
    console.print(f"[dim]Command: {' '.join(command)}[/dim]")

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error serving {remote_path}: {e}[/bold red]")


def serve_local():
    """
    Serves a local directory using rclone.
    """
    local_path = navigate_local_file_system()
    if not local_path:
        return

    backends = choose_from_list(["http", "webdav", "ftp"], "Select the backend to use:")
    if not backends:
        return
    backend = backends[0] if isinstance(backends, list) else backends

    ip_address = get_ip_address()
    port = os.environ.get("DEFAULT_PORT", 8080)
    username = os.environ.get("USERNAME", "user")
    password = os.environ.get("PASSWORD", "pass")

    console.print(
        f"[green]Serving {local_path} on {ip_address}:{port} using {backend}...[/green]"
    )

    command = [
        "rclone",
        "serve",
        backend,
        "--addr",
        f"{ip_address}:{port}",
        "--user",
        username,
        "--pass",
        password,
        local_path,
    ]

    console.print(f"[dim]Command: {' '.join(command)}[/dim]")
    subprocess.run(command)


def upload_backup(overwrite: bool = False):
    """
    Uploads files or a directory to a remote destination.
    """
    console.rule("[bold]⬆️ Upload[/bold]")

    console.print(
        "\n[bold cyan]-- Step 1: Select Local Files/Folder to Upload --[/bold cyan]"
    )
    local_selection = navigate_local_file_system()
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
    remote_dir = navigate_remote_file_system(remote)
    # Ensure the remote path is treated as a directory
    if not remote_dir.endswith("/"):
        remote_dir = remote_dir.strip("/") + "/"

    console.rule(f"[green]Starting Upload[/green]")

    base_command = ["rclone", "copy"]
    if overwrite:
        console.print("[yellow]Overwrite mode enabled.[/yellow]")
        base_command.append("--ignore-times")

    if isinstance(local_selection, str):
        # If it's a single item (file or directory), copy it directly.
        # rclone handles whether it's a file or directory correctly.
        command = base_command + [local_selection, remote_dir, "--progress"]
        subprocess.run(command)
    else:
        # If it's a list of files, we must use the '--files-from' flag
        # This is more efficient than running 'rclone copy' for every single file.
        files_to_upload_list = local_selection

        # We need to get the directory that these files are in
        base_dir = os.path.dirname(files_to_upload_list[0])
        # And just the filenames themselves
        file_names = [os.path.basename(f) for f in files_to_upload_list]

        console.print(f"Uploading {len(file_names)} files from {base_dir}...")

        # Use '--files-from' with '-' to read from stdin
        command = base_command + [
            "--files-from",
            "-",
            base_dir,
            remote_dir,
            "--progress",
        ]

        # Pass the list of filenames to the command
        process = subprocess.Popen(command, stdin=subprocess.PIPE, text=True)
        process.communicate("\n".join(file_names))

    console.rule(f"[bold green]✅ Upload Complete[/bold green]")


def download_backup(overwrite: bool = False):
    """
    Downloads one or more files/directories from a remote destination.
    """
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
    remote_selection = navigate_remote_file_system(remote)
    if not remote_selection:
        return

    console.print(
        "\n[bold cyan]-- Step 3: Select Local Destination Folder --[/bold cyan]"
    )
    local_dir = navigate_local_file_system()
    if not local_dir or os.path.isfile(local_dir):
        console.print("[red]Invalid destination. You must select a directory.[/red]")
        return

    console.rule(f"[green]Starting Download[/green]")

    base_command = ["rclone", "copy"]
    if overwrite:
        console.print("[yellow]Overwrite mode enabled (ignoring timestamps).[/yellow]")
        base_command.append("--ignore-times")

    if isinstance(remote_selection, str):
        console.print(
            f"Downloading {os.path.basename(remote_selection.rstrip('/'))} to {local_dir}..."
        )
        command = base_command + [remote_selection, local_dir, "--progress"]
        subprocess.run(command)
    else:
        files_to_download_list = remote_selection

        if overwrite:
            console.print(
                f"Downloading {len(files_to_download_list)} items one by one to ensure overwrite..."
            )
            for item in files_to_download_list:
                console.print(f"Downloading 📄 {os.path.basename(item.rstrip('/'))}...")
                command = base_command + [item, local_dir, "--progress"]
                subprocess.run(command)
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
                "--progress",
            ]
            process = subprocess.Popen(command, stdin=subprocess.PIPE, text=True)
            process.communicate("\n".join(file_names_only))

    console.rule(f"[bold green]✅ Download Complete[/bold green]")


def manage_config():
    """
    Provides a menu to manage rclone flags in the config.ini file.
    """
    config_path = "config.ini"
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
        console.print("4. Exit")
        choice = Prompt.ask(
            "Enter your choice", choices=["1", "2", "3", "4"], default="4"
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
            remote_type = Prompt.ask(
                "Enter the remote type (e.g., drive, mega)"
            ).lower()
            flag_to_add = Prompt.ask(
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
            remote_type = Prompt.ask("Enter the remote type").lower()
            if not config.has_option("rclone_flags", remote_type):
                console.print(f"[red]No flags found for '{remote_type}'.[/red]")
                continue

            flag_to_delete = Prompt.ask(
                "Enter the flag key to delete (e.g., --vfs-cache-mode)"
            )
            existing_flags = config.get("rclone_flags", remote_type).splitlines()
            new_flags = [f for f in existing_flags if not f.startswith(flag_to_delete)]

            config["rclone_flags"][remote_type] = "\n".join(new_flags)
            save_changes()

        elif choice == "4":
            break


def sync_remotes():
    """
    Syncs between two rclone remotes.
    """
    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    source_remote = choose_from_list(remotes, "Select the source remote:")
    if not source_remote:
        return

    source_path = navigate_remote_file_system(source_remote)
    if not source_path:
        return

    destination_remote = choose_from_list(remotes, "Select the destination remote:")
    if not destination_remote:
        return

    destination_path = navigate_remote_file_system(destination_remote)
    if not destination_path:
        return

    console.print(f"[green]Syncing {source_path} to {destination_path}...[/green]")
    command = ["rclone", "sync", source_path, destination_path, "--progress"]
    subprocess.run(command)


def generate_default_config():
    """
    Generates a default config.ini file with example configuration.
    """
    config_path = os.path.join(PROJECT_ROOT, "config.ini")

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
    }

    # Add rclone_flags section with examples
    config["rclone_flags"] = {
        "mega": "--vfs-cache-mode=full\n--vfs-cache-max-size=1G\n--vfs-cache-max-age=24h",
        "drive": "--vfs-cache-mode=full\n--vfs-cache-max-size=2G",
        "google photos": "--gphotos-read-size\n--vfs-cache-mode=full\n--vfs-cache-max-size=10G\n--vfs-cache-max-age=24h",
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
    local_path = navigate_local_file_system()
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
    remote_path = navigate_remote_file_system(remote)
    if not remote_path:
        return

    console.rule("[green]Running Check[/green]")
    command = ["rclone", "check", local_path, remote_path, "--progress"]
    with console.status("[dim]Checking files...[/dim]"):
        result = subprocess.run(command)

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

    remote = choose_from_list(remotes, "Select remote to browse:")
    if not remote:
        return

    current_path = f"{remote}:"
    while True:
        console.print(f"\n[bold cyan]Path:[/bold cyan] {current_path}")
        try:
            with console.status(f"[dim]Listing {current_path}...[/dim]"):
                output = subprocess.check_output(
                    ["rclone", "lsl", current_path], stderr=subprocess.DEVNULL
                ).decode("utf-8")

            lines = [l for l in output.strip().split("\n") if l]
            if not lines:
                console.print("[dim]-- Empty --[/dim]")
            else:
                for line in lines:
                    console.print(f"  {line}")

            choice = Prompt.ask(
                "\n[yellow]Enter subfolder name to navigate, '..' to go up, or 'q' to quit[/yellow]"
            )

            if choice.lower() == "q":
                break
            elif choice == "..":
                if current_path.strip("/") == f"{remote}:".strip("/"):
                    continue
                current_path = os.path.dirname(current_path.rstrip("/")) + "/"
            else:
                current_path = current_path.rstrip("/") + "/" + choice.strip("/") + "/"

        except subprocess.CalledProcessError:
            console.print("[red]Error listing path. Going back.[/red]")
            current_path = f"{remote}:"


def dedupe_remote():
    """
    Find and remove duplicate files on a remote using rclone dedupe.
    """
    console.rule("[bold]🗑️ Dedupe Remote[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    remote = choose_from_list(remotes, "Select remote to dedupe:")
    if not remote:
        return

    console.print("\n[bold cyan]-- Select Remote Path --[/bold cyan]")
    remote_path = navigate_remote_file_system(remote)
    if not remote_path:
        return

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
        confirm = Prompt.ask(
            "Are you sure? This may delete files. (y/n)",
            choices=["y", "n"],
            default="n",
        )
        if confirm != "y":
            console.print("[dim]Cancelled.[/dim]")
            return

    with console.status(f"[dim]Running dedupe on {remote_path}...[/dim]"):
        command = ["rclone", "dedupe", f"--dedupe-mode={mode}", remote_path]
        subprocess.run(command)
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

    selected = choose_from_list(
        remotes, "Select remote(s) to check (e.g., 1 or 1,2 or 'all'):"
    )
    if not selected:
        return
    if not isinstance(selected, list):
        selected = [selected]

    for remote in selected:
        console.print(f"\n[bold cyan]── {remote} ──[/bold cyan]")
        try:
            with console.status(f"[dim]Fetching quota for {remote}...[/dim]"):
                result = subprocess.run(
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
    source_path = navigate_remote_file_system(source_remote)
    if not source_path:
        return

    console.print("\n[bold cyan]-- Step 3: Select Destination Remote --[/bold cyan]")
    dest_remote = choose_from_list(remotes, "Select destination remote:")
    if not dest_remote:
        return

    console.print("\n[bold cyan]-- Step 4: Select Destination Path --[/bold cyan]")
    dest_path = navigate_remote_file_system(dest_remote)
    if not dest_path:
        return

    console.rule("[green]Starting Remote-to-Remote Copy[/green]")
    console.print(f"[dim]{source_path} → {dest_path}[/dim]")

    command = ["rclone", "copy", source_path, dest_path, "--progress"]
    with console.status(f"[dim]Copying {source_path} → {dest_path}...[/dim]"):
        subprocess.run(command)
    console.rule("[bold green]✅ Copy Complete[/bold green]")


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
    path1 = navigate_remote_file_system(remote1)
    if not path1:
        return

    console.print("\n[bold cyan]-- Step 2: Select Second Remote --[/bold cyan]")
    remote2 = choose_from_list(remotes, "Select second remote:")
    if not remote2:
        return
    path2 = navigate_remote_file_system(remote2)
    if not path2:
        return

    resync = Prompt.ask(
        "\n[yellow]Run with --resync? (required on first run) (y/n)[/yellow]",
        choices=["y", "n"],
        default="n",
    )

    console.rule("[green]Starting Bisync[/green]")
    console.print(f"[dim]{path1} ↔ {path2}[/dim]")

    command = ["rclone", "bisync", path1, path2, "--progress"]
    if resync == "y":
        command.append("--resync")

    with console.status(f"[dim]Syncing {path1} ↔ {path2}...[/dim]"):
        subprocess.run(command)
    console.rule("[bold green]✅ Bisync Complete[/bold green]")
