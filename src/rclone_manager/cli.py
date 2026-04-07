import argparse

from rich.console import Console

from .config import setup_env
from .config import PROJECT_ROOT
from .mount import mount_remote, unmount_remote
from .webui_launcher import main as webui_main
from .sync_pairs import (
    sync_pairs,
    sync_pairs_add,
    sync_pairs_list,
    sync_pairs_run,
    sync_pairs_remove,
)
from .status import show_status
from .core import (
    serve_remote,
    serve_local,
    upload_backup,
    download_backup,
    sync_remotes,
    manage_config,
    manage_filters,
    generate_default_config,
    check_remote,
    ls_remote,
    dedupe_remote,
    space_remote,
    copy_between,
    bisync_remotes,
)

console = Console()


def main():
    """
    The main function of the rclone-scripts CLI.
    """
    setup_env(PROJECT_ROOT)
    parser = argparse.ArgumentParser(description="Rclone Scripts")
    subparsers = parser.add_subparsers(dest="command")

    # Generate config command
    subparsers.add_parser("generate-config", help="Generate a default config.ini file")

    # Serve remote command
    subparsers.add_parser("serve-remote", help="Serve a remote destination")

    # Serve local command
    subparsers.add_parser("serve-local", help="Serve a local directory")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload a backup")
    upload_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files at the destination.",
    )

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a backup")
    download_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files at the destination.",
    )

    # Sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync between two rclone remotes (destructive: makes destination match source)",
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be transferred without making any changes",
    )
    sync_parser.add_argument(
        "--preview",
        action="store_true",
        help="Show files that would be copied/deleted/overwritten before confirming",
    )
    sync_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (use with caution!)",
    )

    # Config command
    subparsers.add_parser("config", help="Manage rclone flags in config.ini")

    # Web UI command
    subparsers.add_parser("web-ui", help="Launch web-based user interface")

    # Mounting
    subparsers.add_parser("mount", help="Mount a remote as a local directory")
    subparsers.add_parser("unmount", help="Unmount active rclone mounts")

    # Additional Utils
    subparsers.add_parser("ls", help="Browse and list contents of a remote")

    subparsers.add_parser("checksum", help="Verify integrity between local and remote")

    subparsers.add_parser("dedupe", help="Find and remove duplicate files on a remote")

    subparsers.add_parser("space", help="Show quota and storage usage for remotes")

    subparsers.add_parser(
        "copy-between", help="Copy files directly between two remotes"
    )

    subparsers.add_parser("bisync", help="Two-way sync between two remotes")

    sync_pairs_parser = subparsers.add_parser(
        "sync-pairs", help="Manage and run sync pairs"
    )
    sync_pairs_parser.add_argument(
        "action",
        nargs="?",
        choices=["add", "list", "run", "remove"],
        help="Action to perform (optional, interactive if omitted)",
    )
    sync_pairs_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be transferred without making any changes",
    )
    subparsers.add_parser("status", help="Show active mounts and sync pairs")

    subparsers.add_parser("filters", help="Manage global exclude/include filters")

    fzf_parser = subparsers.add_parser("fzf", help="Toggle fuzzy search on/off")
    fzf_parser.add_argument(
        "action",
        nargs="?",
        choices=["on", "off", "status"],
        help="Turn fzf on, off, or show current status",
    )

    args = parser.parse_args()

    try:
        if args.command == "serve-remote":
            serve_remote()
        elif args.command == "serve-local":
            serve_local()
        elif args.command == "upload":
            upload_backup(overwrite=args.overwrite)
        elif args.command == "download":
            download_backup(overwrite=args.overwrite)
        elif args.command == "config":
            manage_config()
        elif args.command == "sync":
            if args.dry_run and args.force:
                console.print(
                    "[bold red]Error: --dry-run and --force cannot be used together.[/bold red]"
                )
                return
            sync_remotes(dry_run=args.dry_run, preview=args.preview, force=args.force)
        elif args.command == "generate-config":
            generate_default_config()
        elif args.command == "web-ui":
            webui_main()
        elif args.command == "mount":
            mount_remote()
        elif args.command == "unmount":
            unmount_remote()
        elif args.command == "ls":
            ls_remote()
        elif args.command == "checksum":
            check_remote()
        elif args.command == "dedupe":
            dedupe_remote()
        elif args.command == "space":
            space_remote()
        elif args.command == "copy-between":
            copy_between()
        elif args.command == "bisync":
            bisync_remotes()
        elif args.command == "sync-pairs":
            if hasattr(args, "action") and args.action:
                if args.action == "add":
                    sync_pairs_add()
                elif args.action == "list":
                    sync_pairs_list()
                elif args.action == "run":
                    sync_pairs_run(dry_run=args.dry_run)
                elif args.action == "remove":
                    sync_pairs_remove()
            else:
                sync_pairs()
        elif args.command == "status":
            show_status()
        elif args.command == "filters":
            manage_filters()
        elif args.command == "fzf":
            from .utils import _toggle_fzf

            action = args.action or "status"
            _toggle_fzf(action)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        console.print("\n[bold red]Execution cancelled by user.[/bold red]")


if __name__ == "__main__":
    main()
