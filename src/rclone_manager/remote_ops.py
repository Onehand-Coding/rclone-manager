import json
import logging
import os
import subprocess

from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput
from .stats import _run_rclone_with_stats
from .fzf import _fzf_available, _run_fzf
from .navigation import choose_from_list, navigate_local_file_system, navigate_remote_file_system
from .remote_info import list_rclone_remotes

console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()
logger = logging.getLogger(__name__)


def check_remote(overwrite: bool = False):
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
    console.rule("[bold]📋 List Remote[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    console.print("\n[bold cyan]-- Step 1: Select Remote to Browse --[/bold cyan]")
    remote = choose_from_list(remotes, "Select remote to browse:")
    if not remote:
        return

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
    console.rule("[bold]🗑️ Dedupe Remote[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    console.print("\n[bold cyan]-- Step 1: Select Remote --[/bold cyan]")
    remote = choose_from_list(remotes, "Select remote to dedupe:")
    if not remote:
        return

    console.print("\n[bold cyan]-- Step 2: Select Remote Path --[/bold cyan]")
    remote_path = navigate_remote_file_system(remote, purpose="remote path")
    if not remote_path:
        return

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
    console.rule("[bold]💾 Remote Storage Usage[/bold]")

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

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
