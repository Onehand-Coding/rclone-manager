import json
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

MODES = {
    "upload_only": {
        "label": "Upload Only",
        "description": "Copy local → remote (no deletions)",
        "destructive": False,
    },
    "download_only": {
        "label": "Download Only",
        "description": "Copy remote → local (no deletions)",
        "destructive": False,
    },
    "upload_delete": {
        "label": "Upload + Delete",
        "description": "Sync local → remote (deletes remote files not in local)",
        "destructive": True,
    },
    "download_delete": {
        "label": "Download + Delete",
        "description": "Sync remote → local (deletes local files not in remote)",
        "destructive": True,
    },
    "two_way": {
        "label": "Two-Way",
        "description": "Bisync local ↔ remote",
        "destructive": True,
    },
    "move_to_remote": {
    "label": "Move to Remote",
    "description": "Upload local → remote, delete local after transfer",
    "destructive": True,
    },
    "move_to_local": {
        "label": "Move to Local",
        "description": "Download remote → local, delete remote after transfer",
        "destructive": True,
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
    except Exception:
        return []


def _save_pairs(pairs: list):
    with open(_config_path(), "w") as f:
        json.dump(pairs, f, indent=2)


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_command(pair: dict) -> list:
    """Build rclone command for a sync pair with filters applied."""
    from .config import PROJECT_ROOT, get_filters, build_filter_args

    local = pair["local"]
    remote = pair["remote"]
    mode = pair["mode"]

    # Get global filters and merge with pair-specific filters
    global_filters = get_filters(PROJECT_ROOT)
    pair_filters = pair.get("filters", {})

    # Merge filters (pair filters extend global filters)
    exclude = global_filters["exclude"] + pair_filters.get("exclude", [])
    include = global_filters["include"] + pair_filters.get("include", [])
    merged_filters = {"exclude": exclude, "include": include}

    # Build base command
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
        # Note: bisync has its own filter handling
        cmd.extend(build_filter_args(merged_filters))
        return cmd
    else:
        return []

    # Add filter arguments
    cmd.extend(build_filter_args(merged_filters))
    return cmd


def _confirm_run(pair: dict) -> bool:
    mode_info = MODES[pair["mode"]]
    tag = "[bold red]DESTRUCTIVE[/bold red]" if mode_info["destructive"] else "[green]SAFE[/green]"
    console.print(f"\n[bold]Sync Pair:[/bold] {pair['name']}")
    console.print(f"  Mode   : {mode_info['label']} ({tag})")
    console.print(f"  Action : {mode_info['description']}")
    console.print(f"  Local  : {pair['local']}")
    console.print(f"  Remote : {pair['remote']}")
    return Confirm.ask("\nProceed?", default=False)


# ── public commands ───────────────────────────────────────────────────────────

def sync_pairs_add():
    """Interactively add a new sync pair."""
    console.print("\n[bold cyan]Add Sync Pair[/bold cyan]")

    # Name
    name = Prompt.ask("Pair name (e.g. Work Docs)")
    if not name:
        return

    # Check duplicate
    pairs = _load_pairs()
    if any(p["name"] == name for p in pairs):
        console.print(f"[red]A pair named '{name}' already exists.[/red]")
        return

    # Local path
    console.print("\n[bold]Select local folder:[/bold]")
    local = navigate_local_file_system()
    if not local or isinstance(local, list):
        console.print("[red]Invalid local path.[/red]")
        return
    if not os.path.isdir(local):
        console.print("[red]Local path must be a directory.[/red]")
        return

    # Remote
    remotes = list_rclone_remotes()
    if not remotes:
        return
    remote_name = choose_from_list(remotes, "Select remote:")
    if not remote_name or isinstance(remote_name, list):
        return

    # Remote path
    console.print(f"\n[bold]Navigate to folder on {remote_name}:[/bold]")
    console.print("[dim]Press '.' or 'd' to select current directory[/dim]")
    remote_path = navigate_remote_file_system(remote_name)
    if not remote_path or isinstance(remote_path, list):
        console.print("[red]Invalid remote path.[/red]")
        return
    # Normalize: strip trailing slash for consistency
    remote_path = remote_path.rstrip("/")

    # Mode
    mode_keys = list(MODES.keys())
    mode_labels = [f"{MODES[k]['label']} — {MODES[k]['description']}" for k in mode_keys]
    selected_mode_label = choose_from_list(mode_labels, "Select sync mode:")
    if not selected_mode_label:
        return
    mode = mode_keys[mode_labels.index(selected_mode_label)]

    # Optional: Add pair-specific filters
    console.print("\n[dim]Add pair-specific exclude patterns? (comma-separated, or skip)[/dim]")
    console.print("[dim]Examples: *.log, temp/, drafts/[/dim]")
    exclude_input = Prompt.ask("Exclude patterns", default="")
    
    pair_filters = {}
    if exclude_input.strip():
        patterns = [p.strip() for p in exclude_input.split(",") if p.strip()]
        if patterns:
            pair_filters["exclude"] = patterns
    
    console.print("\n[dim]Add pair-specific include patterns? (comma-separated, or skip)[/dim]")
    console.print("[dim]Examples: important/*, projects/*.pdf[/dim]")
    include_input = Prompt.ask("Include patterns", default="")
    
    if include_input.strip():
        patterns = [p.strip() for p in include_input.split(",") if p.strip()]
        if patterns:
            pair_filters["include"] = patterns

    pair = {
        "name": name,
        "local": local,
        "remote": remote_path,
        "mode": mode,
        "bisync_resync_done": False,
    }
    
    if pair_filters:
        pair["filters"] = pair_filters

    pairs.append(pair)
    _save_pairs(pairs)
    console.print(f"\n[green]✅ Sync pair '{name}' added.[/green]")


def sync_pairs_list():
    """Display all configured sync pairs."""
    pairs = _load_pairs()
    if not pairs:
        console.print("[yellow]No sync pairs configured. Use 'rman sync-pairs add'.[/yellow]")
        return

    table = Table(title="Sync Pairs", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold")
    table.add_column("Mode")
    table.add_column("Local")
    table.add_column("Remote")
    table.add_column("Filters", style="dim")

    for i, p in enumerate(pairs, 1):
        mode_info = MODES.get(p["mode"], {})
        label = mode_info.get("label", p["mode"])
        destructive = mode_info.get("destructive", False)
        mode_display = f"[red]{label}[/red]" if destructive else f"[green]{label}[/green]"
        
        # Show filters if configured
        filters = p.get("filters", {})
        filter_str = ""
        if filters.get("exclude"):
            filter_str += f"[yellow]Exclude: {', '.join(filters['exclude'])}[/yellow]\n"
        if filters.get("include"):
            filter_str += f"[cyan]Include: {', '.join(filters['include'])}[/cyan]"
        
        table.add_row(str(i), p["name"], mode_display, p["local"], p["remote"], filter_str)

    console.print(table)


def sync_pairs_run():
    """Run one or all sync pairs."""
    pairs = _load_pairs()
    if not pairs:
        console.print("[yellow]No sync pairs configured. Use 'rman sync-pairs add'.[/yellow]")
        return

    options = ["All"] + [p["name"] for p in pairs]
    selected = choose_from_list(options, "Select pair(s) to run:")
    if not selected:
        return

    if selected == "All":
        to_run = pairs
    elif isinstance(selected, list):
        to_run = [p for p in pairs if p["name"] in selected]
    else:
        to_run = [p for p in pairs if p["name"] == selected]

    for pair in to_run:
        if not _confirm_run(pair):
            console.print(f"[dim]Skipped {pair['name']}.[/dim]")
            continue

        command = _build_command(pair)
        console.print(f"\n[dim]Command: {' '.join(command)}[/dim]")

        label = MODES[pair['mode']]['label']
        returncode, errors = _run_rclone_with_stats(label, command)

        if returncode == 0:
            console.print(f"[green]✅ {pair['name']} completed.[/green]")
            if pair["mode"] == "two_way" and not pair.get("bisync_resync_done"):
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
            if pair["mode"] == "two_way":
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
