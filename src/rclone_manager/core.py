import os
import logging
from configparser import ConfigParser

from .config import get_project_root, get_filters
from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput

# Re-export from new modules for backward compatibility

console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()
logger = logging.getLogger(__name__)


def generate_default_config():
    config_path = os.path.join(get_project_root(), "configs", "config.ini")

    if os.path.exists(config_path):
        console.print(
            "[yellow]config.ini already exists. Remove it first to generate a new one.[/yellow]"
        )
        return

    config = ConfigParser()

    config["DEFAULT"] = {
        "LOG_LEVEL": "INFO",
        "LOG_FILE": "logs/rclone_scripts.log",
        "DEFAULT_PORT": "8080",
        "USERNAME": "your_username",
        "PASSWORD": "your_secret_password",
        "INCLUDE_HIDDEN": "false",
    }

    config["rclone_flags"] = {
        "mega": "--vfs-cache-mode=full\n--vfs-cache-max-size=1G\n--vfs-cache-max-age=24h",
        "drive": "--vfs-cache-mode=full\n--vfs-cache-max-size=2G",
        "google photos": "--gphotos-read-size\n--vfs-cache-mode=full\n--vfs-cache-max-size=10G\n--vfs-cache-max-age=24h",
    }

    config["filters"] = {
        "exclude": "\n".join(
            [
                "node_modules/",
                "__pycache__/",
                "*.pyc",
                "*.tmp",
                "*.swp",
            ]
        )
    }

    with open(config_path, "w") as configfile:
        config.write(configfile)

    console.print(
        f"[green]Successfully created default config at {config_path}[/green]"
    )


def manage_config():
    config_path = os.path.join(get_project_root(), "configs", "config.ini")
    config = ConfigParser()
    config.read(config_path)

    if "rclone_flags" not in config:
        config["rclone_flags"] = {}

    def save_changes():
        with open(config_path, "w") as f:
            config.write(f)
        console.print("[green]Configuration saved successfully![/green]")

    while True:
        console.print("\n[bold cyan]--- Configuration Management ---[/bold cyan]")
        console.print("1. View Current Flags")
        console.print("2. Add/Edit Flag for a Remote Type")
        console.print("3. Delete Flag from a Remote Type")
        console.print(
            "4. Toggle Hidden Files (currently: {})".format(
                "included"
                if os.environ.get("INCLUDE_HIDDEN", "false").lower() == "true"
                else "excluded"
            )
        )
        console.print("5. Exit")
        choice = console.input(
            "Enter your choice", choices=["1", "2", "3", "4", "5"], default="5"
        )

        if choice == "1":
            for remote_type, flags in config["rclone_flags"].items():
                console.print(f"\n[bold]{remote_type}[/bold]:")
                for flag in flags.splitlines():
                    if flag:
                        console.print(f"  {flag}")
            input("\nPress Enter to continue...")

        elif choice == "2":
            remote_type = console.input(
                "Enter the remote type (e.g., drive, mega)"
            ).lower()
            flag_to_add = console.input(
                "Enter the full flag to add/edit (e.g., --vfs-cache-mode=full)"
            )

            existing_flags = config.get(
                "rclone_flags", remote_type, fallback=""
            ).splitlines()
            flag_key = flag_to_add.split("=")[0]

            new_flags = [f for f in existing_flags if not f.startswith(flag_key)]
            new_flags.append(flag_to_add)

            config["rclone_flags"][remote_type] = "\n".join(new_flags)
            save_changes()

        elif choice == "3":
            remote_type = console.input("Enter the remote type").lower()
            if not config.has_option("rclone_flags", remote_type):
                console.print(f"[red]No flags found for '{remote_type}'.[/red]")
                continue

            flag_to_delete = console.input(
                "Enter the flag key to delete (e.g., --vfs-cache-mode)"
            )
            existing_flags = config.get("rclone_flags", remote_type).splitlines()
            new_flags = [f for f in existing_flags if not f.startswith(flag_to_delete)]

            config["rclone_flags"][remote_type] = "\n".join(new_flags)
            save_changes()

        elif choice == "4":
            current = config.get("DEFAULT", "INCLUDE_HIDDEN", fallback="false")
            new_val = "true" if current.lower() == "false" else "false"
            config["DEFAULT"]["INCLUDE_HIDDEN"] = new_val
            os.environ["INCLUDE_HIDDEN"] = new_val
            save_changes()
            console.print(
                f"[green]Hidden files are now {'included' if new_val == 'true' else 'excluded'}.[/green]"
            )

        elif choice == "5":
            break


def manage_filters():
    root = get_project_root()
    config_path = os.path.join(root, "configs", "config.ini")

    def load_config():
        config = ConfigParser()
        config.read(config_path)
        return config

    def save_config(config):
        with open(config_path, "w") as f:
            config.write(f)

    while True:
        filters = get_filters(root)

        console.print("\n[bold cyan]--- Filter Management ---[/bold cyan]")
        console.print("\n[bold]Current Exclude Patterns:[/bold]")
        if filters["exclude"]:
            for i, pattern in enumerate(filters["exclude"], 1):
                console.print(f"  {i}. [yellow]{pattern}[/yellow]")
        else:
            console.print("  [dim]None[/dim]")

        console.print("\n[bold]Current Include Patterns:[/bold]")
        if filters["include"]:
            for i, pattern in enumerate(filters["include"], 1):
                console.print(f"  {i}. [cyan]{pattern}[/cyan]")
        else:
            console.print("  [dim]None[/dim]")

        console.print("\n1. Add Exclude Pattern")
        console.print("2. Remove Exclude Pattern")
        console.print("3. Add Include Pattern")
        console.print("4. Remove Include Pattern")
        console.print("5. Reset to Defaults")
        console.print("6. Exit")

        choice = console.input(
            "\nEnter your choice", choices=["1", "2", "3", "4", "5", "6"], default="6"
        )

        if choice == "1":
            pattern = console.input("Enter exclude pattern (e.g., *.log, node_modules/)")
            if pattern:
                config = load_config()
                if "filters" not in config:
                    config["filters"] = {}
                current = config["filters"].get("exclude", "")
                patterns = [p.strip() for p in current.split("\n") if p.strip()]
                patterns.append(pattern)
                config["filters"]["exclude"] = "\n".join(patterns)
                save_config(config)
                console.print(f"[green]✅ Added exclude pattern: {pattern}[/green]")

        elif choice == "2":
            if not filters["exclude"]:
                console.print("[yellow]No exclude patterns to remove.[/yellow]")
                continue
            selected = console.input(
                "Select pattern to remove",
                choices=[str(i) for i in range(1, len(filters["exclude"]) + 1)],
            )
            idx = int(selected) - 1
            config = load_config()
            current = config["filters"].get("exclude", "")
            patterns = [p.strip() for p in current.split("\n") if p.strip()]
            removed = patterns.pop(idx)
            config["filters"]["exclude"] = "\n".join(patterns) if patterns else ""
            save_config(config)
            console.print(f"[green]✅ Removed: {removed}[/green]")

        elif choice == "3":
            pattern = console.input("Enter include pattern (e.g., important/*, *.pdf)")
            if pattern:
                config = load_config()
                if "filters" not in config:
                    config["filters"] = {}
                current = config["filters"].get("include", "")
                patterns = [p.strip() for p in current.split("\n") if p.strip()]
                patterns.append(pattern)
                config["filters"]["include"] = "\n".join(patterns)
                save_config(config)
                console.print(f"[green]✅ Added include pattern: {pattern}[/green]")

        elif choice == "4":
            if not filters["include"]:
                console.print("[yellow]No include patterns to remove.[/yellow]")
                continue
            selected = console.input(
                "Select pattern to remove",
                choices=[str(i) for i in range(1, len(filters["include"]) + 1)],
            )
            idx = int(selected) - 1
            config = load_config()
            current = config["filters"].get("include", "")
            patterns = [p.strip() for p in current.split("\n") if p.strip()]
            removed = patterns.pop(idx)
            config["filters"]["include"] = "\n".join(patterns) if patterns else ""
            save_config(config)
            console.print(f"[green]✅ Removed: {removed}[/green]")

        elif choice == "5":
            if (
                console.input(
                    "Reset to default patterns?", choices=["y", "n"], default="n"
                )
                == "y"
            ):
                config = load_config()
                if "filters" not in config:
                    config["filters"] = {}
                defaults = [
                    "node_modules/",
                    "__pycache__/",
                    "*.pyc",
                    "*.tmp",
                    "*.swp",
                ]
                config["filters"]["exclude"] = "\n".join(defaults)
                config["filters"]["include"] = ""
                save_config(config)
                console.print("[green]✅ Reset to default patterns.[/green]")

        elif choice == "6":
            console.print("[dim]Exiting filter management.[/dim]")
            break
