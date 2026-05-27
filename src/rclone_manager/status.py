import json
import logging
import os

from rich.table import Table
from rich import box

from .ports import OutputPort, RichOutput
from .utils import (
    _is_windows,
    _get_mount_base,
    _load_registry,
    _rc_vfs_stats,
)

console: OutputPort = RichOutput()
logger = logging.getLogger(__name__)


# ── helpers (duplicated minimally to avoid circular imports) ──────────────────


def _is_mount_point(path: str) -> bool:
    """Cross-platform mount point check."""
    if os.path.ismount(path):
        return True
    if _is_windows():
        return os.path.isdir(path)
    return False


def _sync_pairs_path() -> str:
    """Get the path to sync-pairs.json in the project's configs directory."""
    from .config import get_project_root

    return os.path.join(get_project_root(), "configs", "sync-pairs.json")


def _load_sync_pairs() -> list:
    try:
        with open(_sync_pairs_path()) as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in sync-pairs.json: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to load sync pairs: {e}")
        return []


def _pending_transfers(port: int) -> int:
    stats = _rc_vfs_stats(port)
    if not stats:
        return -1  # rc unavailable
    disk_cache = stats.get("diskCache", {})
    return (
        disk_cache.get("uploadsInProgress", 0)
        + disk_cache.get("uploadsQueued", 0)
        + disk_cache.get("downloadsInProgress", 0)
        + disk_cache.get("downloadsQueued", 0)
    )


# ── public ────────────────────────────────────────────────────────────────────


def show_status():
    mount_base = _get_mount_base()
    registry = _load_registry()
    sync_pairs = _load_sync_pairs()

    console.rule("[bold cyan]rclone-manager status[/bold cyan]")

    # ── Mounts ────────────────────────────────────────────────────────────────
    active_mounts = []
    if os.path.exists(mount_base):
        active_mounts = [
            d
            for d in os.listdir(mount_base)
            if _is_mount_point(os.path.join(mount_base, d))
        ]

    if active_mounts:
        mount_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        mount_table.add_column("", width=2)
        mount_table.add_column("Name", style="bold")
        mount_table.add_column("Mount Point", style="dim")
        mount_table.add_column("RC Port", style="dim")
        mount_table.add_column("Transfers")

        for name in sorted(active_mounts):
            mp = os.path.join(mount_base, name)
            port = registry.get(name)
            port_str = f":{port}" if port else "n/a"

            if port:
                pending = _pending_transfers(port)
                if pending == -1:
                    transfer_str = "[dim]rc unavailable[/dim]"
                elif pending == 0:
                    transfer_str = "[green]idle[/green]"
                else:
                    transfer_str = f"[yellow]⚠ {pending} pending[/yellow]"
            else:
                transfer_str = "[dim]—[/dim]"

            mount_table.add_row("●", name, mp, port_str, transfer_str)

        console.print(f"\n[bold] Mounts[/bold]  [dim]{len(active_mounts)} active[/dim]")
        console.print(mount_table)
    else:
        console.print("\n[bold] Mounts[/bold]  [dim]none active[/dim]")

    # ── Sync Pairs ────────────────────────────────────────────────────────────
    MODE_LABELS = {
        "upload_only": ("Upload Only", "green"),
        "download_only": ("Download Only", "green"),
        "upload_delete": ("Upload + Delete", "red"),
        "download_delete": ("Download + Delete", "red"),
        "two_way": ("Two-Way", "red"),
        "move_to_remote": ("Move to Remote", "red"),
        "move_to_local": ("Move to Local", "red"),
        "remote_copy": ("Remote Copy", "green"),
        "remote_sync_delete": ("Remote Sync + Delete", "red"),
        "remote_move": ("Remote Move", "red"),
        "remote_bisync": ("Remote Bisync", "red"),
    }

    if sync_pairs:
        pairs_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        pairs_table.add_column("", width=2)
        pairs_table.add_column("Name", style="bold")
        pairs_table.add_column("Mode")
        pairs_table.add_column("Source", style="dim")
        pairs_table.add_column("", width=3)
        pairs_table.add_column("Destination", style="dim")

        for pair in sync_pairs:
            label, color = MODE_LABELS.get(pair["mode"], (pair["mode"], "white"))
            pair_type = pair.get("type", "local_to_remote")
            if pair_type == "remote_to_remote":
                source = pair.get("source", "")
                destination = pair.get("destination", "")
            else:
                source = pair.get("local", "")
                destination = pair.get("remote", "")

            pairs_table.add_row(
                "▸",
                pair["name"],
                f"[{color}]{label}[/{color}]",
                source,
                "→",
                destination,
            )

        console.print(
            f"[bold] Sync Pairs[/bold]  [dim]{len(sync_pairs)} configured[/dim]"
        )
        console.print(pairs_table)
    else:
        console.print("[bold] Sync Pairs[/bold]  [dim]none configured[/dim]")

    console.rule()
