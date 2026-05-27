import logging

from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput
from .stats import _run_rclone_with_stats
from .navigation import choose_from_list, navigate_remote_file_system
from .remote_info import list_rclone_remotes

console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()
logger = logging.getLogger(__name__)


def sync_remotes(dry_run: bool = False, preview: bool = False, force: bool = False):
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

    console.print("\n[yellow]⚠️  DESTRUCTIVE OPERATION[/yellow]")
    console.print(f"[yellow]Source:      {source_path}[/yellow]")
    console.print(f"[yellow]Destination: {destination_path}[/yellow]")
    console.print(
        "[yellow]Files on destination not in source will be DELETED permanently.[/yellow]\n"
    )

    if preview:
        console.print("[bold]Running preview (rclone check)...[/bold]\n")
        try:
            result_src = _runner.run(
                ["rclone", "check", source_path, destination_path, "--missing-on-dst"],
                capture_output=True,
                text=True,
            )

            result_dst = _runner.run(
                ["rclone", "check", source_path, destination_path, "--missing-on-src"],
                capture_output=True,
                text=True,
            )

            result_diff = _runner.run(
                ["rclone", "check", source_path, destination_path],
                capture_output=True,
                text=True,
            )

            only_in_source = []
            only_in_dest = []
            differ = []

            for line in result_src.stderr.strip().split("\n"):
                if not line.strip():
                    continue
                if "file not in one directory" in line or "file not in Remote" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        path = parts[1].strip()
                        only_in_source.append(path)

            for line in result_dst.stderr.strip().split("\n"):
                if not line.strip():
                    continue
                if "file not in one directory" in line or "file not in Local" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        path = parts[1].strip()
                        only_in_dest.append(path)

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

    if dry_run:
        console.print("[dim]Dry run mode: No changes will be made.[/dim]\n")
    elif not force:
        from rich.prompt import Confirm

        if not Confirm.ask("[bold red]Proceed with sync?[/bold red]", default=False):
            console.print("[dim]Sync cancelled.[/dim]")
            return

    command = ["rclone", "sync", source_path, destination_path]
    if dry_run:
        command.append("--dry-run")

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
