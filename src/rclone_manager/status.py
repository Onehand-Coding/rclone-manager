import json
import os
import subprocess

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


# ── helpers (duplicated minimally to avoid circular imports) ──────────────────

def _get_mount_base() -> str:
    return os.path.expanduser(os.environ.get("MOUNT_DIR", "~/mnt"))


def _registry_path() -> str:
    return os.path.join(_get_mount_base(), ".rc_ports.json")


def _load_registry() -> dict:
    try:
        with open(_registry_path()) as f:
            return json.load(f)
    except Exception:
        return {}


def _sync_pairs_path() -> str:
    """Get the path to sync-pairs.json in the project's configs directory."""
    from .config import PROJECT_ROOT
    return os.path.join(PROJECT_ROOT, "configs", "sync-pairs.json")


def _load_sync_pairs() -> list:
    try:
        with open(_sync_pairs_path()) as f:
            return json.load(f)
    except Exception:
        return []


def _rc_vfs_stats(port: int) -> dict | None:
    try:
        result = subprocess.run(
            ["rclone", "rc", "vfs/stats", f"--rc-addr=127.0.0.1:{port}"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def _pending_transfers(port: int) -> int:
    stats = _rc_vfs_stats(port)
    if not stats:
        return -1  # rc unavailable
    disk_cache = stats.get("diskCache", {})
    return (
        disk_cache.get("uploadsInProgress", 0) +
        disk_cache.get("uploadsQueued", 0) +
        disk_cache.get("downloadsInProgress", 0) +
        disk_cache.get("downloadsQueued", 0)
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
            d for d in os.listdir(mount_base)
            if os.path.ismount(os.path.join(mount_base, d))
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
        "upload_only":     ("Upload Only",      "green"),
        "download_only":   ("Download Only",    "green"),
        "upload_delete":   ("Upload + Delete",  "red"),
        "download_delete": ("Download + Delete","red"),
        "two_way":         ("Two-Way",          "red"),
        "move_to_remote":  ("Move to Remote",   "red"),
        "move_to_local":   ("Move to Local",    "red"),
    }

    if sync_pairs:
        pairs_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        pairs_table.add_column("", width=2)
        pairs_table.add_column("Name", style="bold")
        pairs_table.add_column("Mode")
        pairs_table.add_column("Local", style="dim")
        pairs_table.add_column("", width=3)
        pairs_table.add_column("Remote", style="dim")

        for pair in sync_pairs:
            label, color = MODE_LABELS.get(pair["mode"], (pair["mode"], "white"))
            pairs_table.add_row(
                "▸",
                pair["name"],
                f"[{color}]{label}[/{color}]",
                pair["local"],
                "→",
                pair["remote"],
            )

        console.print(f"[bold] Sync Pairs[/bold]  [dim]{len(sync_pairs)} configured[/dim]")
        console.print(pairs_table)
    else:
        console.print("[bold] Sync Pairs[/bold]  [dim]none configured[/dim]")

    console.rule()
