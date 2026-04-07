import json
import logging
import os

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .utils import (
    _run_rclone_with_stats,
    choose_from_list,
    list_rclone_remotes,
    navigate_local_file_system,
    navigate_remote_file_system,
)

console = Console()
logger = logging.getLogger(__name__)

MODES = {
    # Local to Remote modes
    "upload_only": {
        "label": "Upload Only",
        "description": "Copy local → remote (no deletions)",
        "destructive": False,
        "type": "local_to_remote",
    },
    "download_only": {
        "label": "Download Only",
        "description": "Copy remote → local (no deletions)",
        "destructive": False,
        "type": "local_to_remote",
    },
    "upload_delete": {
        "label": "Upload + Delete",
        "description": "Sync local → remote (deletes remote files not in local)",
        "destructive": True,
        "type": "local_to_remote",
    },
    "download_delete": {
        "label": "Download + Delete",
        "description": "Sync remote → local (deletes local files not in remote)",
        "destructive": True,
        "type": "local_to_remote",
    },
    "two_way": {
        "label": "Two-Way",
        "description": "Bisync local ↔ remote",
        "destructive": True,
        "type": "local_to_remote",
    },
    "move_to_remote": {
        "label": "Move to Remote",
        "description": "Upload local → remote, delete local after transfer",
        "destructive": True,
        "type": "local_to_remote",
    },
    "move_to_local": {
        "label": "Move to Local",
        "description": "Download remote → local, delete remote after transfer",
        "destructive": True,
        "type": "local_to_remote",
    },
    # Remote to Remote modes
    "remote_copy": {
        "label": "Remote Copy",
        "description": "Copy remote1 → remote2 (no deletions, server-side when possible)",
        "destructive": False,
        "type": "remote_to_remote",
    },
    "remote_sync_delete": {
        "label": "Remote Sync + Delete",
        "description": "Sync remote1 → remote2 (deletes extra files on remote2)",
        "destructive": True,
        "type": "remote_to_remote",
    },
    "remote_move": {
        "label": "Remote Move",
        "description": "Move remote1 → remote2 (deletes source after transfer)",
        "destructive": True,
        "type": "remote_to_remote",
    },
    "remote_bisync": {
        "label": "Remote Bisync",
        "description": "Bidirectional sync remote1 ↔ remote2",
        "destructive": True,
        "type": "remote_to_remote",
    },
}


# ── storage ───────────────────────────────────────────────────────────────────


def _config_path() -> str:
    """Get the path to sync-pairs.json in the project's configs directory."""
    from .config import PROJECT_ROOT

    return os.path.join(PROJECT_ROOT, "configs", "sync-pairs.json")


def _load_pairs() -> list:
    try:
        with open(_config_path()) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in sync-pairs.json: {e}")
        return []
    except FileNotFoundError:
        logger.info("No sync-pairs.json found, starting fresh")
        return []
    except Exception as e:
        logger.error(f"Failed to load sync pairs: {e}")
        return []


def _save_pairs(pairs: list):
    with open(_config_path(), "w") as f:
        json.dump(pairs, f, indent=2)


# ── helpers ───────────────────────────────────────────────────────────────────


def _build_command(pair: dict, dry_run: bool = False) -> list:
    """Build rclone command for a sync pair with filters applied."""
    from .config import PROJECT_ROOT, get_filters, build_filter_args

    pair_type = pair.get("type", "local_to_remote")
    mode = pair["mode"]

    source = pair.get("source", "")
    destination = pair.get("destination", "")
    local = pair.get("local", "")
    remote = pair.get("remote", "")

    global_filters = get_filters(PROJECT_ROOT)
    pair_filters = pair.get("filters", {})

    exclude = global_filters["exclude"] + pair_filters.get("exclude", [])
    include = global_filters["include"] + pair_filters.get("include", [])
    merged_filters = {"exclude": exclude, "include": include}

    if pair_type == "local_to_remote":
        if mode == "upload_only":
            cmd = ["rclone", "copy", local, remote]
        elif mode == "download_only":
            cmd = ["rclone", "copy", remote, local]
        elif mode == "upload_delete":
            cmd = ["rclone", "sync", local, remote]
        elif mode == "download_delete":
            cmd = ["rclone", "sync", remote, local]
        elif mode == "two_way":
            cmd = ["rclone", "bisync", local, remote]
            if not pair.get("bisync_resync_done") or os.name == "nt":
                cmd.append("--resync")
            cmd.extend(build_filter_args(merged_filters))
            if dry_run:
                cmd.append("--dry-run")
            return cmd
        elif mode == "move_to_remote":
            cmd = ["rclone", "move", local, remote]
        elif mode == "move_to_local":
            cmd = ["rclone", "move", remote, local]
        else:
            return []
    else:
        if mode == "remote_copy":
            cmd = ["rclone", "copy", source, destination]
        elif mode == "remote_sync_delete":
            cmd = ["rclone", "sync", source, destination]
        elif mode == "remote_move":
            cmd = ["rclone", "move", source, destination]
        elif mode == "remote_bisync":
            cmd = ["rclone", "bisync", source, destination]
            if not pair.get("bisync_resync_done"):
                cmd.append("--resync")
            cmd.extend(build_filter_args(merged_filters))
            if dry_run:
                cmd.append("--dry-run")
            return cmd
        else:
            return []

    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(build_filter_args(merged_filters))
    return cmd


def _confirm_run(pair: dict) -> bool:
    mode_info = MODES[pair["mode"]]
    tag = (
        "[bold red]DESTRUCTIVE[/bold red]"
        if mode_info["destructive"]
        else "[green]SAFE[/green]"
    )

    # Determine pair type (default to local_to_remote for backward compatibility)
    pair_type = pair.get("type", "local_to_remote")

    console.print(f"\n[bold]Sync Pair:[/bold] {pair['name']}")
    console.print(
        f"  Type   : {'[cyan]Remote→Remote[/cyan]' if pair_type == 'remote_to_remote' else '[magenta]Local→Remote[/magenta]'}"
    )
    console.print(f"  Mode   : {mode_info['label']} ({tag})")
    console.print(f"  Action : {mode_info['description']}")

    if pair_type == "remote_to_remote":
        console.print(f"  Source      : {pair.get('source', '')}")
        console.print(f"  Destination : {pair.get('destination', '')}")
    else:
        console.print(f"  Local  : {pair.get('local', '')}")
        console.print(f"  Remote : {pair.get('remote', '')}")

    return Confirm.ask("\nProceed?", default=False)


# ── public commands ───────────────────────────────────────────────────────────


def sync_pairs_add():
    """Interactively add a new sync pair."""
    console.print("\n[bold cyan]═══ Add Sync Pair ═══[/bold cyan]")

    # Step 1: Name
    console.print("\n[bold cyan]-- Step 1: Enter Pair Name --[/bold cyan]")
    name = Prompt.ask("Pair name (e.g. Work Docs, Drive to Mega Backup)")
    if not name:
        return

    # Check duplicate
    pairs = _load_pairs()
    if any(p["name"] == name for p in pairs):
        console.print(f"[red]A pair named '{name}' already exists.[/red]")
        return

    # Step 2: Select Pair Type
    console.print("\n[bold cyan]-- Step 2: Select Pair Type --[/bold cyan]")
    pair_types = [
        ("local_to_remote", "Local → Remote", "Sync local folder with remote storage"),
        (
            "remote_to_remote",
            "Remote → Remote",
            "Sync between two remote storages (server-side when possible)",
        ),
    ]
    type_labels = [f"{label} — {desc}" for _, label, desc in pair_types]
    selected_type_label = choose_from_list(type_labels, "Select pair type:")
    if not selected_type_label:
        return
    pair_type = pair_types[type_labels.index(selected_type_label)][0]

    if pair_type == "local_to_remote":
        # Local to Remote workflow
        console.print("\n[bold cyan]-- Step 3: Select Local Folder --[/bold cyan]")
        local = navigate_local_file_system(purpose="folder")
        if not local or isinstance(local, list):
            console.print("[red]Invalid local path.[/red]")
            return
        if not os.path.isdir(local):
            console.print("[red]Local path must be a directory.[/red]")
            return

        console.print("\n[bold cyan]-- Step 4: Select Remote --[/bold cyan]")
        remotes = list_rclone_remotes()
        if not remotes:
            return
        remote_name = choose_from_list(remotes, "Select remote:")
        if not remote_name or isinstance(remote_name, list):
            return

        console.print("\n[bold cyan]-- Step 5: Select Remote Path --[/bold cyan]")
        console.print(f"[dim]Navigating: {remote_name}[/dim]")
        console.print("[dim]Press '.' or 'd' to select current directory[/dim]")
        remote_path = navigate_remote_file_system(remote_name, purpose="remote folder")
        if not remote_path or isinstance(remote_path, list):
            console.print("[red]Invalid remote path.[/red]")
            return
        remote_path = remote_path.rstrip("/")

        # Filter modes for local_to_remote
        available_modes = [
            (k, v) for k, v in MODES.items() if v.get("type") == "local_to_remote"
        ]

    else:  # remote_to_remote
        console.print("\n[bold cyan]-- Step 3: Select Source Remote --[/bold cyan]")
        remotes = list_rclone_remotes()
        if not remotes:
            return
        source_remote = choose_from_list(remotes, "Select source remote:")
        if not source_remote or isinstance(source_remote, list):
            return

        console.print("\n[bold cyan]-- Step 4: Select Source Path --[/bold cyan]")
        console.print(f"[dim]Navigating: {source_remote}[/dim]")
        console.print("[dim]Press '.' or 'd' to select current directory[/dim]")
        source_path = navigate_remote_file_system(source_remote, purpose="source path")
        if not source_path or isinstance(source_path, list):
            console.print("[red]Invalid source path.[/red]")
            return
        source_path = source_path.rstrip("/")

        console.print(
            "\n[bold cyan]-- Step 5: Select Destination Remote --[/bold cyan]"
        )
        dest_remote = choose_from_list(remotes, "Select destination remote:")
        if not dest_remote or isinstance(dest_remote, list):
            return

        console.print("\n[bold cyan]-- Step 6: Select Destination Path --[/bold cyan]")
        console.print(f"[dim]Navigating: {dest_remote}[/dim]")
        console.print("[dim]Press '.' or 'd' to select current directory[/dim]")
        dest_path = navigate_remote_file_system(dest_remote, purpose="destination path")
        if not dest_path or isinstance(dest_path, list):
            console.print("[red]Invalid destination path.[/red]")
            return
        dest_path = dest_path.rstrip("/")

        # Filter modes for remote_to_remote
        available_modes = [
            (k, v) for k, v in MODES.items() if v.get("type") == "remote_to_remote"
        ]
        local = None
        remote_path = None

    # Step N: Select Mode
    console.print(
        "\n[bold cyan]-- Step {}: Select Sync Mode --[/bold cyan]".format(
            6 if pair_type == "local_to_remote" else 7
        )
    )
    mode_labels = [f"{v['label']} — {v['description']}" for k, v in available_modes]
    mode_keys = [k for k, v in available_modes]
    selected_mode_label = choose_from_list(mode_labels, "Select sync mode:")
    if not selected_mode_label:
        return
    mode = mode_keys[mode_labels.index(selected_mode_label)]

    # Optional: Add pair-specific filters
    console.print(
        "\n[dim]Add pair-specific exclude patterns? (comma-separated, or skip)[/dim]"
    )
    console.print("[dim]Examples: *.log, temp/, drafts/[/dim]")
    exclude_input = Prompt.ask("Exclude patterns", default="")

    pair_filters = {}
    if exclude_input.strip():
        patterns = [p.strip() for p in exclude_input.split(",") if p.strip()]
        if patterns:
            pair_filters["exclude"] = patterns

    console.print(
        "\n[dim]Add pair-specific include patterns? (comma-separated, or skip)[/dim]"
    )
    console.print("[dim]Examples: important/*, projects/*.pdf[/dim]")
    include_input = Prompt.ask("Include patterns", default="")

    if include_input.strip():
        patterns = [p.strip() for p in include_input.split(",") if p.strip()]
        if patterns:
            pair_filters["include"] = patterns

    # Build pair object
    pair = {
        "name": name,
        "type": pair_type,
        "mode": mode,
        "bisync_resync_done": False,
    }

    if pair_type == "local_to_remote":
        pair["local"] = local
        pair["remote"] = remote_path
    else:  # remote_to_remote
        pair["source"] = source_path
        pair["destination"] = dest_path

    if pair_filters:
        pair["filters"] = pair_filters

    pairs.append(pair)
    _save_pairs(pairs)
    console.print(f"\n[green]✅ Sync pair '{name}' added.[/green]")


def sync_pairs_list():
    """Display all configured sync pairs."""
    pairs = _load_pairs()
    if not pairs:
        console.print(
            "[yellow]No sync pairs configured. Use 'rman sync-pairs add'.[/yellow]"
        )
        return

    table = Table(title="Sync Pairs", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Mode")
    table.add_column("Source/Local")
    table.add_column("", width=3)
    table.add_column("Destination/Remote")
    table.add_column("Filters", style="dim")

    for i, p in enumerate(pairs, 1):
        # Determine pair type (default to local_to_remote for backward compatibility)
        pair_type = p.get("type", "local_to_remote")

        mode_info = MODES.get(p["mode"], {})
        label = mode_info.get("label", p["mode"])
        destructive = mode_info.get("destructive", False)
        mode_display = (
            f"[red]{label}[/red]" if destructive else f"[green]{label}[/green]"
        )

        # Get paths based on pair type
        if pair_type == "remote_to_remote":
            type_display = "[cyan]Remote→Remote[/cyan]"
            source = p.get("source", "")
            destination = p.get("destination", "")
        else:  # local_to_remote
            type_display = "[magenta]Local→Remote[/magenta]"
            source = p.get("local", "")
            destination = p.get("remote", "")

        # Show filters if configured
        filters = p.get("filters", {})
        filter_str = ""
        if filters.get("exclude"):
            filter_str += f"[yellow]Exclude: {', '.join(filters['exclude'])}[/yellow]\n"
        if filters.get("include"):
            filter_str += f"[cyan]Include: {', '.join(filters['include'])}[/cyan]"

        table.add_row(
            str(i),
            p["name"],
            type_display,
            mode_display,
            source,
            "→",
            destination,
            filter_str,
        )

    console.print(table)


def sync_pairs_run(dry_run: bool = False):
    """Run one or all sync pairs."""
    pairs = _load_pairs()
    if not pairs:
        console.print(
            "[yellow]No sync pairs configured. Use 'rman sync-pairs add'.[/yellow]"
        )
        return

    options = ["All"] + [p["name"] for p in pairs]
    selected = choose_from_list(options, "Select pair(s) to run:", multi=True)
    if not selected:
        return

    if selected == "All":
        to_run = pairs
    elif isinstance(selected, list):
        to_run = [p for p in pairs if p["name"] in selected]
    else:
        to_run = [p for p in pairs if p["name"] == selected]

    for pair in to_run:
        if not dry_run and not _confirm_run(pair):
            console.print(f"[dim]Skipped {pair['name']}.[/dim]")
            continue

        command = _build_command(pair, dry_run=dry_run)
        if not command:
            console.print(
                f"[red]❌ Unknown mode '{pair['mode']}' for pair {pair['name']}. Skipping.[/red]"
            )
            continue

        console.print(f"\n[dim]Command: {' '.join(command)}[/dim]")

        if dry_run:
            console.print("[yellow]🔍 Dry-run mode - no changes will be made[/yellow]")
            import subprocess

            result = subprocess.run(command, capture_output=True, text=True)
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[dim]{result.stderr}[/dim]")
            continue

        label = MODES[pair["mode"]]["label"]
        returncode, errors = _run_rclone_with_stats(label, command)

        if returncode == 0:
            console.print(f"[green]✅ {pair['name']} completed.[/green]")
            if pair["mode"] in ["two_way", "remote_bisync"] and not pair.get(
                "bisync_resync_done"
            ):
                all_pairs = _load_pairs()
                for p in all_pairs:
                    if p["name"] == pair["name"]:
                        p["bisync_resync_done"] = True
                _save_pairs(all_pairs)
        else:
            console.print(f"[red]❌ {pair['name']} failed (exit {returncode}).[/red]")
            if errors:
                for e in errors:
                    console.print(f"[red]   {e}[/red]")
            if pair["mode"] in ["two_way", "remote_bisync"]:
                all_pairs = _load_pairs()
                for p in all_pairs:
                    if p["name"] == pair["name"]:
                        p["bisync_resync_done"] = False
                _save_pairs(all_pairs)


def sync_pairs_remove():
    """Remove a sync pair."""
    pairs = _load_pairs()
    if not pairs:
        console.print("[yellow]No sync pairs configured.[/yellow]")
        return

    names = [p["name"] for p in pairs]
    selected = choose_from_list(names, "Select pair to remove:")
    if not selected or isinstance(selected, list):
        return

    pair = next((p for p in pairs if p["name"] == selected), None)
    if not pair:
        return

    if not Confirm.ask(f"Remove '{selected}'?", default=False):
        return

    pairs = [p for p in pairs if p["name"] != selected]
    _save_pairs(pairs)
    console.print(f"[green]✅ Removed '{selected}'.[/green]")


def sync_pairs():
    """Entry point — dispatch to add/list/run/remove."""
    actions = ["add", "list", "run", "remove"]
    action = choose_from_list(actions, "What would you like to do?")
    if not action:
        return

    if action == "add":
        sync_pairs_add()
    elif action == "list":
        sync_pairs_list()
    elif action == "run":
        sync_pairs_run()
    elif action == "remove":
        sync_pairs_remove()
