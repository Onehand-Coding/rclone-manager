import json
import os
import shutil
import socket
import subprocess
import time

from rich.console import Console
from rich.prompt import Prompt

from .utils import (
    choose_from_list,
    get_remote_type,
    get_rclone_flags,
    list_rclone_remotes,
)

console = Console()

# Backends that don't support FUSE mount
UNSUPPORTED_TYPES = ("google-photos", "cloudinary")
UNSUPPORTED_NAMES = ("gphotos", "google photos", "cloudinary")


# ── internal helpers ──────────────────────────────────────────────────────────


def _get_mount_base() -> str:
    return os.path.expanduser(os.environ.get("MOUNT_DIR", "~/mnt"))


def _fusermount_cmd() -> str:
    """Return fusermount3 if available (Fedora/newer), fall back to fusermount."""
    return "fusermount3" if shutil.which("fusermount3") else "fusermount"


def _find_free_port(start: int = 5572) -> int:
    """Find a free TCP port starting from start."""
    port = start
    while port < 5700:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start


def _rc_stats(port: int) -> dict | None:
    """Query rclone rc vfs/stats. Returns dict or None if unavailable."""
    try:
        result = subprocess.run(
            ["rclone", "rc", "vfs/stats", f"--rc-addr=127.0.0.1:{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def _registry_path() -> str:
    return os.path.join(_get_mount_base(), ".rc_ports.json")


def _load_registry() -> dict:
    try:
        with open(_registry_path()) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_registry(registry: dict):
    path = _registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(registry, f, indent=2)


def _remove_from_registry(name: str):
    registry = _load_registry()
    registry.pop(name, None)
    _save_registry(registry)


def _is_unsupported(remote: str, remote_type: str) -> bool:
    name_lower = remote.lower()
    type_lower = remote_type.lower()
    return any(u in type_lower for u in UNSUPPORTED_TYPES) or any(
        u in name_lower for u in UNSUPPORTED_NAMES
    )


def _check_pending_uploads(port: int, name: str) -> str:
    """
    Check for pending uploads via rc. Returns 'ok', 'cancel', or 'force'.
    Only prompts if there are actually pending uploads.
    """
    stats = _rc_stats(port)
    if stats is None:
        return "ok"  # rc unavailable, proceed silently

    disk_cache = stats.get("diskCache", {})
    in_progress = disk_cache.get("uploadsInProgress", 0) + disk_cache.get(
        "downloadsInProgress", 0
    )
    queued = disk_cache.get("uploadsQueued", 0) + disk_cache.get("downloadsQueued", 0)
    pending = (
        disk_cache.get("uploadsInProgress", 0)
        + disk_cache.get("uploadsQueued", 0)
        + disk_cache.get("downloadsInProgress", 0)
        + disk_cache.get("downloadsQueued", 0)
    )

    if pending == 0:
        return "ok"

    console.print(
        f"\n[bold yellow]⚠️  {name} has {pending} transfer(s) still pending "
        f"({in_progress} in progress, {queued} queued).[/bold yellow]"
    )
    choice = Prompt.ask(
        "What would you like to do?",
        choices=["wait", "force", "cancel"],
        default="wait",
    )

    if choice == "cancel":
        return "cancel"

    if choice == "wait":
        with console.status("") as status:
            while True:
                time.sleep(3)
                stats = _rc_stats(port)
                if stats is None:
                    break
                disk_cache = stats.get("diskCache", {})
                pending = disk_cache.get("uploadsInProgress", 0) + disk_cache.get(
                    "uploadsQueued", 0
                )
                status.update(f"[dim]Transferring... {pending} remaining[/dim]")
                if pending == 0:
                    break
        console.print("[green]✅ All transfers complete.[/green]")

    return "ok"  # wait completed or force


# ── public functions ──────────────────────────────────────────────────────────


def mount_remote():
    """
    Mount one or more rclone remotes as local directories via FUSE.
    - Skips unsupported backends (gphotos, cloudinary)
    - Enables rc on a unique port per mount for upload status checks
    - Polls os.path.ismount() to confirm mount is ready
    - Saves rc port registry for use by unmount
    """
    if not shutil.which("fusermount3") and not shutil.which("fusermount"):
        console.print(
            "[bold red]❌ FUSE not available on this system. "
            "Use serve-remote instead.[/bold red]"
        )
        return

    mount_base = _get_mount_base()
    os.makedirs(mount_base, exist_ok=True)

    remotes = list_rclone_remotes()
    if not remotes:
        console.print("[bold red]No rclone remotes found.[/bold red]")
        return

    selected = choose_from_list(remotes, "Select remote(s) to mount:")
    if not selected:
        return
    if not isinstance(selected, list):
        selected = [selected]

    # Filter unsupported backends
    valid = []
    for remote in selected:
        remote_type = get_remote_type(remote)
        if _is_unsupported(remote, remote_type):
            console.print(
                f"[yellow]⚠️  Skipping [bold]{remote}[/bold] — "
                f"not supported for mount. Use serve-remote instead.[/yellow]"
            )
        else:
            valid.append((remote, remote_type))

    if not valid:
        return

    registry = _load_registry()

    for remote, remote_type in valid:
        mount_key = remote.replace(" ", "_")
        mount_point = os.path.join(mount_base, mount_key)

        # Skip if already mounted
        if os.path.ismount(mount_point):
            console.print(
                f"[yellow]⚠️  {remote} is already mounted at {mount_point}. Skipping.[/yellow]"
            )
            continue

        # Clean up stale empty dir if present
        if os.path.exists(mount_point):
            try:
                os.rmdir(mount_point)
            except OSError:
                pass  # non-empty, leave it
        os.makedirs(mount_point, exist_ok=True)

        flags = get_rclone_flags(remote_type)
        rc_port = _find_free_port(5572)

        command = [
            "rclone",
            "mount",
            f"{remote}:",
            mount_point,
            "--rc",
            f"--rc-addr=127.0.0.1:{rc_port}",
        ] + flags

        console.print(
            f"\n[green]Mounting [bold]{remote}[/bold] → {mount_point}[/green]"
        )
        console.print(f"[dim]Command: {' '.join(command)}[/dim]")

        proc = subprocess.Popen(command)

        # Poll until mounted or process dies
        mounted = False
        with console.status(f"[dim]Waiting for {remote} to mount...[/dim]"):
            for _ in range(30):
                time.sleep(1)
                if os.path.ismount(mount_point):
                    mounted = True
                    break
                if proc.poll() is not None:
                    break  # process exited early — failed

        if mounted:
            registry[mount_key] = rc_port
            console.print(
                f"[bold green]✅ Mounted {remote} → {mount_point} "
                f"(rc port {rc_port})[/bold green]"
            )
        else:
            console.print(
                f"[bold red]❌ Failed to mount {remote}. "
                f"Exit code: {proc.returncode}[/bold red]"
            )
            proc.terminate()
            try:
                os.rmdir(mount_point)
            except OSError:
                pass

    _save_registry(registry)
    console.print(f"\n[dim]To unmount: rman unmount[/dim]")


def unmount_remote():
    """
    Unmount active rclone mounts.
    - Checks for pending uploads before unmounting (if rc available)
    - Falls back to lazy unmount (-uz) if normal unmount fails
    - Cleans up empty mount point directories and registry entries
    """
    mount_base = _get_mount_base()

    if not os.path.exists(mount_base):
        console.print("[yellow]No mounts directory found.[/yellow]")
        return

    active = [
        d
        for d in os.listdir(mount_base)
        if os.path.ismount(os.path.join(mount_base, d))
    ]

    if not active:
        console.print("[yellow]No active mounts found.[/yellow]")
        return

    options = ["All"] + active
    selected = choose_from_list(options, "Select mount(s) to unmount:")
    if not selected:
        return

    if selected == "All":
        to_unmount = active
    elif isinstance(selected, list):
        to_unmount = selected
    else:
        to_unmount = [selected]

    registry = _load_registry()
    fusermount = _fusermount_cmd()

    for name in to_unmount:
        mp = os.path.join(mount_base, name)
        rc_port = registry.get(name)

        # Check pending uploads before unmounting
        if rc_port:
            outcome = _check_pending_uploads(rc_port, name)
            if outcome == "cancel":
                console.print(f"[dim]Skipped {name}.[/dim]")
                continue

        # Attempt clean unmount
        result = subprocess.run([fusermount, "-u", mp], capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[green]✅ Unmounted {mp}[/green]")
            _finalize_unmount(mp, name)
        else:
            error = result.stderr.strip()
            console.print(
                f"[yellow]⚠️  Clean unmount failed: {error}. Trying lazy unmount...[/yellow]"
            )

            # Fallback: lazy unmount (-uz detaches even if busy)
            lazy = subprocess.run(
                [fusermount, "-uz", mp], capture_output=True, text=True
            )
            if lazy.returncode == 0:
                console.print(f"[yellow]⚠️  Lazy unmount succeeded for {mp}[/yellow]")
                _finalize_unmount(mp, name)
            else:
                console.print(
                    f"[red]❌ Failed to unmount {mp}: {lazy.stderr.strip()}[/red]"
                )


def _finalize_unmount(mp: str, name: str):
    """Clean up mount point directory and registry after successful unmount."""
    try:
        os.rmdir(mp)
        console.print(f"[dim]Removed {mp}[/dim]")
    except OSError:
        pass
    _remove_from_registry(name)
