import os
import re
import socket
import subprocess
from typing import List, Union
from rich.console import Console
from rich.prompt import Prompt

console = Console()


def get_ip_address() -> str:
    """
    Returns the local IP address of the machine.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP


def list_rclone_remotes() -> List[str]:
    """
    Returns a list of all rclone remotes, filtering out remotes ending in '-shared'.
    """
    try:
        output = subprocess.check_output(["rclone", "listremotes"]).decode("utf-8")
        remotes = [
            line.strip().replace(":", "") for line in output.strip().split("\n")
        ]
        # Filter out the shared remotes to avoid duplicates in the list
        return [r for r in remotes if not r.endswith("-shared")]
    except FileNotFoundError:
        console.print("[bold red]rclone not found. Please install it.[/bold red]")
        return []


def get_remote_type(remote: str) -> str:
    """
    Returns the type of a given rclone remote.
    """
    try:
        output = subprocess.check_output(
            ["rclone", "config", "show", f"{remote}:"]
        ).decode("utf-8")
        match = re.search(r"type\s*=\s*(.*)", output)
        if match:
            return match.group(1).strip()
        return ""
    except subprocess.CalledProcessError:
        return ""


def get_rclone_flags(remote_type: str) -> List[str]:
    """
    Returns a list of rclone flags for a given remote type.
    """
    flags = os.environ.get(f"RCLONE_FLAGS_{remote_type.upper()}", "")
    return flags.split()


def choose_from_list(items: List[str], message: str, item_type: str = "items") -> Union[List[str], str]:
    """
    Prompts the user to choose one or more items from a list.
    Returns a single item if one is chosen, otherwise a list.
    """
    if not items:
        console.print(f"[bold red]No {item_type} found in this directory.[/bold red]")
        return None

    for i, item in enumerate(items):
        # Display directories with a trailing slash
        display_item = f"{item}/" if item.endswith("/") else item
        console.print(f"{i+1}. {display_item}")

    choices_str = Prompt.ask(f"[yellow]{message}[/yellow]")
    if not choices_str:
        return None

    selected_indices = [int(i.strip()) - 1 for i in choices_str.split(",")]
    selected_items = [items[i] for i in selected_indices]

    return selected_items[0] if len(selected_items) == 1 else selected_items


def navigate_local_file_system() -> Union[List[str], str]:
    """
    Allows the user to navigate the local file system and select files or a directory.
    """
    current_dir = os.path.expanduser("~")
    while True:
        try:
            all_items = sorted([item for item in os.listdir(current_dir) if not item.startswith('.')])

            dirs = [d for d in all_items if os.path.isdir(os.path.join(current_dir, d))]
            files = [f for f in all_items if os.path.isfile(os.path.join(current_dir, f))]

            console.print(f"\n[bold cyan]Current Directory:[/bold cyan] {current_dir}")

            items = dirs + files
            for i, item in enumerate(items):
                if item in dirs:
                    console.print(f"{i+1}. 📁 {item}/")
                else:
                    console.print(f"{i+1}. 📄 {item}")

            prompt = "[yellow]Navigate by number, '..' (up), or select items (e.g., 1 or 2,3). Press '.' or 'd' to select this directory.[/yellow]"
            choice = Prompt.ask(prompt)

            if choice == "..":
                current_dir = os.path.dirname(current_dir)
                continue

            elif choice.lower() in ['.', 'd']:
                return current_dir

            selected_indices = [int(i.strip()) - 1 for i in choice.split(",")]
            selected_items = [items[i] for i in selected_indices]

            if len(selected_items) == 1 and selected_items[0] in dirs:
                current_dir = os.path.join(current_dir, selected_items[0])
            else:
                full_paths = [os.path.join(current_dir, item) for item in selected_items]
                return full_paths[0] if len(full_paths) == 1 else full_paths

        except (ValueError, IndexError):
            console.print("[bold red]Invalid choice.[/bold red]")
        except FileNotFoundError:
            console.print("[bold red]Directory not found.[/bold red]")
            current_dir = os.path.expanduser("~")


def navigate_remote_file_system(remote: str) -> Union[List[str], str]:
    """
    Allows the user to navigate a remote file system and select one or more files/directories.
    """
    current_path = f"{remote}:"
    while True:
        try:
            output = subprocess.check_output(["rclone", "lsf", current_path]).decode("utf-8")
            items = sorted(output.strip().split("\n"))

            console.print(f"\n[bold cyan]Current Remote Path:[/bold cyan] {current_path}")

            if not any(items):
                console.print("[dim]-- Empty --[/dim]")

            for i, item in enumerate(items):
                if item.endswith("/"):
                    console.print(f"{i+1}. 📁 {item}")
                else:
                    console.print(f"{i+1}. 📄 {item}")

            prompt = "[yellow]Navigate (number), go up (..), or select items (e.g., 1,2). Press '.' or 'd' to select this path.[/yellow]"
            choice = Prompt.ask(prompt)

            if choice.lower() in ['.', 'd']:
                return current_path
            elif choice == "..":
                if current_path.strip('/') == f"{remote}:".strip('/'):
                    continue
                current_path = os.path.dirname(current_path.rstrip('/')) + "/"
            else:
                # --- Handle multiple selections ---
                selected_indices = [int(i.strip()) - 1 for i in choice.split(",")]
                selected_items = [items[i] for i in selected_indices]

                # If user selected a single directory, navigate into it
                if len(selected_items) == 1 and selected_items[0].endswith("/"):
                    current_path += selected_items[0]
                else:
                    # User has selected one or more files/folders, return their full paths
                    full_paths = [current_path + item for item in selected_items]
                    return full_paths[0] if len(full_paths) == 1 else full_paths

        except (ValueError, IndexError):
            console.print("[bold red]Invalid choice.[/bold red]")
        except subprocess.CalledProcessError:
            console.print("[bold red]Error listing remote directory.[/bold red]")
            return current_path
