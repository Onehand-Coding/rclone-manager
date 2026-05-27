import json
import logging
import os
import shutil
import socket
import subprocess
import time

from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput

from .navigation import choose_from_list
from .remote_info import get_remote_type, get_rclone_flags, list_rclone_remotes
from .utils import sanitize_command
from .mount_helpers import _is_windows, _get_mount_base, _registry_path, _load_registry, _rc_vfs_stats

console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()
logger = logging.getLogger(__name__)

# Backends that don't support FUSE mount
UNSUPPORTED_TYPES = ("google-photos", "cloudinary")
UNSUPPORTED_NAMES = ("gphotos", "google photos", "cloudinary")


# ── internal helpers ──────────────────────────────────────────────────────────


def _fusermount_cmd() -> str:
    """Return fusermount3 if available (Fedora/newer), fall back to fusermount."""
    return "fusermount3" if shutil.which("fusermount3") else "fusermount"


def _is_mount_active(mount_point: str, proc: subprocess.Popen | None = None) -> bool:
    """Cross-platform check if a mount point is active."""
    if os.path.ismount(mount_point):
        return True
    if _is_windows() and proc is not None and proc.poll() is None:
        return os.path.isdir(mount_point)
    return False


def _find_free_port(start: int = 5572) -> int:
    """Find a free TCP port starting from start."""
    port = start
    while port < 5700:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start


def _get_registry_entry(registry: dict, name: str) -> tuple:
    """Extract (rc_port, pid) from registry. Handles old format (int) and new format (dict)."""
    entry = registry.get(name)
    if isinstance(entry, dict):
        return entry.get("rc_port"), entry.get("pid")
    return entry, None  # old format: just the port number


def _unmount_via_rc(rc_port: int, mount_point: str) -> bool:
    """Try to unmount via rclone rc API. Works cross-platform."""
    try:
        result = _runner.run(
            ["rclone", "rc", "mount/unmount", f"--rc-addr=127.0.0.1:{rc_port}",
             f"mountPoint={mount_point}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True
        logger.debug(f"rc unmount failed: {result.stderr.strip()}")
    except Exception as e:
        logger.debug(f"rc unmount error: {e}")
    return False


def _save_registry(registry: dict):
    path = _registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(registry, f, indent=2)

    # Restrict permissions to owner-only
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError as e:
            logger.warning("Failed to set permissions on mount registry: %s", e)


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
    stats = _rc_vfs_stats(port)
    if stats is None:
        return "ok"  # rc unavailable, proceed silently

    disk_cache = stats.get("diskCache", {})
    in_progress = disk_cache.get("uploadsInProgress", 0) + disk_cache.get(
        "downloadsInProgress", 0
    )
    queued = disk_cache.get("uploadsQueued", 0) + disk_cache.get("downloadsQueued", 0)
    pending = in_progress + queued

    if pending == 0:
        return "ok"

    console.print(
        f"\n[bold yellow]⚠️  {name} has {pending} transfer(s) still pending "
        f"({in_progress} in progress, {queued} queued).[/bold yellow]"
    )
    choice = console.input(
        "What would you like to do?"
    )

    if choice == "cancel":
        return "cancel"

    if choice == "wait":
        with console.status("") as status:
            while True:
                time.sleep(3)
                stats = _rc_vfs_stats(port)
                if stats is None:
                    break
                disk_cache = stats.get("diskCache", {})
                pending = (
                    disk_cache.get("uploadsInProgress", 0)
                    + disk_cache.get("uploadsQueued", 0)
                    + disk_cache.get("downloadsInProgress", 0)
                    + disk_cache.get("downloadsQueued", 0)
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
    if _is_windows():
        if not shutil.which("rclone"):
            console.print(
                "[bold red]❌ rclone not found. Please install it.[/bold red]"
            )
            return
        # WinFsp is a kernel driver — rclone will error clearly if missing
    elif not shutil.which("fusermount3") and not shutil.which("fusermount"):
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

    # Step 1: Select Remote(s) to Mount
    console.print("\n[bold cyan]-- Step 1: Select Remote(s) to Mount --[/bold cyan]")
    selected = choose_from_list(remotes, "Select remote(s) to mount:", multi=True)
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
        if _is_mount_active(mount_point):
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
        console.print(f"[dim]Command: {' '.join(sanitize_command(command))}[/dim]")

        proc = _runner.popen(command)

        # Poll until mounted or process dies
        mounted = False
        with console.status(f"[dim]Waiting for {remote} to mount...[/dim]"):
            for _ in range(30):
                time.sleep(1)
                if _is_mount_active(mount_point, proc):
                    mounted = True
                    break
                if proc.poll() is not None:
                    break  # process exited early — failed

        if mounted:
            registry[mount_key] = {"rc_port": rc_port, "pid": proc.pid}
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
    console.print("\n[dim]To unmount: rman unmount[/dim]")


def unmount_remote():
    """
    Unmount active rclone mounts.
    - Checks for pending uploads before unmounting (if rc available)
    - Tries rclone rc mount/unmount first (cross-platform)
    - Falls back to fusermount (Unix) or taskkill (Windows)
    - Cleans up empty mount point directories and registry entries
    """
    mount_base = _get_mount_base()

    if not os.path.exists(mount_base):
        console.print("[yellow]No mounts directory found.[/yellow]")
        return

    active = [
        d
        for d in os.listdir(mount_base)
        if _is_mount_active(os.path.join(mount_base, d))
    ]

    if not active:
        console.print("[yellow]No active mounts found.[/yellow]")
        return

    options = ["All"] + active
    selected = choose_from_list(options, "Select mount(s) to unmount:", multi=True)
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
        rc_port, pid = _get_registry_entry(registry, name)

        # Check pending uploads before unmounting
        if rc_port:
            outcome = _check_pending_uploads(rc_port, name)
            if outcome == "cancel":
                console.print(f"[dim]Skipped {name}.[/dim]")
                continue

        unmounted = False

        # Try rc-based unmount first (works on all platforms when rc available)
        if rc_port:
            console.print("[dim]Unmounting via rc...[/dim]")
            if _unmount_via_rc(rc_port, mp):
                console.print(f"[green]✅ Unmounted {mp}[/green]")
                _finalize_unmount(mp, name)
                unmounted = True

        # Fall back to platform-specific unmount
        if not unmounted:
            if _is_windows():
                if pid:
                    result = _runner.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        capture_output=True, text=True,
                    )
                    if result.returncode == 0:
                        console.print(f"[green]✅ Unmounted {mp}[/green]")
                        _finalize_unmount(mp, name)
                        unmounted = True
                    else:
                        console.print(
                            f"[red]❌ Failed to unmount {mp}: "
                            f"{result.stderr.strip()}[/red]"
                        )
                else:
                    console.print(
                        f"[yellow]⚠️  No PID recorded for {name}. "
                        f"Kill rclone.exe manually in Task Manager.[/yellow]"
                    )
            else:
                # Unix: fusermount
                result = _runner.run(
                    [fusermount, "-u", mp], capture_output=True, text=True
                )
                if result.returncode == 0:
                    console.print(f"[green]✅ Unmounted {mp}[/green]")
                    _finalize_unmount(mp, name)
                    unmounted = True
                else:
                    error = result.stderr.strip()
                    console.print(
                        f"[yellow]⚠️  Clean unmount failed: {error}. "
                        f"Trying lazy unmount...[/yellow]"
                    )
                    lazy = _runner.run(
                        [fusermount, "-uz", mp], capture_output=True, text=True
                    )
                    if lazy.returncode == 0:
                        console.print(
                            f"[yellow]⚠️  Lazy unmount succeeded for {mp}[/yellow]"
                        )
                        _finalize_unmount(mp, name)
                        unmounted = True
                    else:
                        console.print(
                            f"[red]❌ Failed to unmount {mp}: "
                            f"{lazy.stderr.strip()}[/red]"
                        )


def _finalize_unmount(mp: str, name: str):
    """Clean up mount point directory and registry after successful unmount."""
    try:
        os.rmdir(mp)
        console.print(f"[dim]Removed {mp}[/dim]")
    except OSError:
        pass
    _remove_from_registry(name)
