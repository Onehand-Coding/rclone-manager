import argparse
from rich.console import Console
from .core import (
    serve_remote,
    serve_local,
    upload_backup,
    download_backup,
    sync_remotes,
)

console = Console()


def main():
    """
    The main function of the rclone-scripts CLI.
    """
    parser = argparse.ArgumentParser(description="Rclone Scripts")
    subparsers = parser.add_subparsers(dest="command")

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
        else:
            parser.print_help()
    except KeyboardInterrupt:
        console.print("\n[bold red]Execution cancelled by user.[/bold red]")


if __name__ == "__main__":
    main()
