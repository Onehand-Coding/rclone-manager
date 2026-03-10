import argparse
from rich.console import Console
from .config import setup_env
from .config import PROJECT_ROOT
from .core import (
    serve_remote,
    serve_local,
    upload_backup,
    download_backup,
    sync_remotes,
    mount_remote,
    unmount_remote,
    manage_config,
    generate_default_config,
    check_remote,
    ls_remote,
    dedupe_remote,
    space_remote,
    copy_between,
    bisync_remotes,
)
from .webui_launcher import main as webui_main


console = Console()


def main():
    """
    The main function of the rclone-scripts CLI.
    """
    setup_env(PROJECT_ROOT)
    parser = argparse.ArgumentParser(description="Rclone Scripts")
    subparsers = parser.add_subparsers(dest="command")

    # Generate config command
    generate_parser = subparsers.add_parser(
    "generate-config", help="Generate a default config.ini file"
    )

    # Serve remote command
    serve_remote_parser = subparsers.add_parser(
        "serve-remote", help="Serve a remote destination"
    )

    # Serve local command
    serve_local_parser = subparsers.add_parser(
        "serve-local", help="Serve a local directory"
    )

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload a backup")
    upload_parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files at the destination."
    )

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a backup")
    download_parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files at the destination."
    )

    # Sync command
    sync_parser = subparsers.add_parser(
        "sync", help="Sync between two rclone remotes"
    )

    # Config command
    config_parser = subparsers.add_parser(
        "config", help="Manage rclone flags in config.ini"
    )

    # Web UI command
    webui_parser = subparsers.add_parser(
        "web-ui", help="Launch web-based user interface"
    )

    # Mounting
    mount_parser = subparsers.add_parser("mount", help="Mount a remote as a local directory")
    unmount_parser = subparsers.add_parser("unmount", help="Unmount active rclone mounts")

    # Additional Utils
    ls_parser = subparsers.add_parser("ls", help="Browse and list contents of a remote")

    checksum_parser = subparsers.add_parser("checksum", help="Verify integrity between local and remote")

    dedupe_parser = subparsers.add_parser("dedupe", help="Find and remove duplicate files on a remote")

    space_parser = subparsers.add_parser("space", help="Show quota and storage usage for remotes")

    copy_between_parser = subparsers.add_parser("copy-between", help="Copy files directly between two remotes")

    bisync_parser = subparsers.add_parser("bisync", help="Two-way sync between two remotes")

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
            sync_remotes()
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
        else:
            parser.print_help()
    except KeyboardInterrupt:
        console.print("\n[bold red]Execution cancelled by user.[/bold red]")


if __name__ == "__main__":
    main()
