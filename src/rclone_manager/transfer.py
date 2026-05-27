import os
import logging

from .config import get_project_root, get_filters, build_filter_args
from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput
from .utils import (
    _run_rclone_with_stats,
    choose_from_list,
    navigate_local_file_system,
    navigate_remote_file_system,
    list_rclone_remotes,
)

console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()
logger = logging.getLogger(__name__)


def upload_backup(overwrite: bool = False):
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

    if isinstance(remote_dir, list):
        remote_dir = remote_dir[0]
    if not remote_dir.endswith("/"):
        remote_dir = remote_dir.strip("/") + "/"

    console.print(
        "\n[dim]Add exclude patterns for this upload? (comma-separated, or skip)[/dim]"
    )
    console.print("[dim]Examples: *.log, temp/, __pycache__/[/dim]")
    exclude_input = console.input("Exclude patterns", default="")
    temp_filters = []
    if exclude_input.strip():
        temp_filters = [p.strip() for p in exclude_input.split(",") if p.strip()]

    console.rule("[green]Starting Upload[/green]")

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

    console.print(
        "\n[dim]Add exclude patterns for this download? (comma-separated, or skip)[/dim]"
    )
    console.print("[dim]Examples: *.tmp, .cache/, Thumbs.db[/dim]")
    exclude_input = console.input("Exclude patterns", default="")
    temp_filters = []
    if exclude_input.strip():
        temp_filters = [p.strip() for p in exclude_input.split(",") if p.strip()]

    console.rule("[green]Starting Download[/green]")

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
