import os
import subprocess
import logging
from typing import List, Union, Optional

from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput
from .fzf import _fzf_available, _run_fzf

logger = logging.getLogger(__name__)
console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()


def choose_from_list(
    items: List[str],
    message: str,
    item_type: str = "items",
    allow_quit: bool = True,
    multi: bool = False,
) -> Union[List[str], str, None]:
    if not items:
        console.print(f"[bold red]No {item_type} found in this directory.[/bold red]")
        return None

    if _fzf_available():
        selected = _run_fzf(items, prompt=message, multi=multi)
        if not selected:
            console.print("[dim]Cancelled.[/dim]")
            return None
        return selected[0] if len(selected) == 1 else selected

    while True:
        for i, item in enumerate(items):
            display_item = f"{item}/" if item.endswith("/") else item
            console.print(f"{i + 1}. {display_item}")

        choices_str = console.input(f"[yellow]{message}[/yellow]")

        if allow_quit and choices_str and choices_str.lower() in ["q", "quit"]:
            console.print("[dim]Cancelled.[/dim]")
            return None

        if not choices_str:
            console.print("[bold red]Please enter a number or 'q' to quit.[/bold red]")
            continue

        if any(not i.strip().isdigit() for i in choices_str.split(",")):
            console.print(
                "[bold red]Invalid choice. Please enter numbers only (e.g., 1 or 1,2).[/bold red]"
            )
            continue

        selected_indices = [int(i.strip()) - 1 for i in choices_str.split(",")]
        if any(i < 0 or i >= len(items) for i in selected_indices):
            console.print(
                f"[bold red]Invalid choice. Please enter numbers between 1 and {len(items)}.[/bold red]"
            )
            continue

        selected_items = [items[i] for i in selected_indices]
        return selected_items[0] if len(selected_items) == 1 else selected_items


def navigate_local_file_system(
    purpose: Optional[str] = None, single_only: bool = False
) -> Union[List[str], str, None]:
    current_dir = os.path.expanduser("~")
    while True:
        try:
            all_items = sorted(
                [item for item in os.listdir(current_dir) if not item.startswith(".")]
            )

            dirs = [d for d in all_items if os.path.isdir(os.path.join(current_dir, d))]
            files = [
                f for f in all_items if os.path.isfile(os.path.join(current_dir, f))
            ]

            items = dirs + files

            if _fzf_available():
                display_items = []
                for item in items:
                    if item in dirs:
                        display_items.append(f"\U0001f4c1 {item}/")
                    else:
                        display_items.append(f"\U0001f4c4 {item}")
                display_items.append(".. (go up)")
                display_items.append(f". (select this {purpose or 'directory'})")

                selected = _run_fzf(
                    display_items, prompt=f"\U0001f4c2 {current_dir} > ", multi=not single_only
                )
                if not selected:
                    console.print("[dim]Cancelled.[/dim]")
                    return None

                selected_items = [
                    s
                    for s in selected
                    if s
                    not in (".. (go up)", f". (select this {purpose or 'directory'})")
                ]

                if len(selected_items) > 1:
                    result_paths = []
                    dirs_to_navigate = []
                    for item in selected_items:
                        name = item[2:].rstrip("/")
                        full_path = os.path.join(current_dir, name)
                        if name in dirs:
                            dirs_to_navigate.append(name)
                        else:
                            result_paths.append(full_path)
                    if dirs_to_navigate:
                        if len(dirs_to_navigate) == 1 and not result_paths:
                            current_dir = os.path.join(current_dir, dirs_to_navigate[0])
                            continue
                        else:
                            for d in dirs_to_navigate:
                                result_paths.append(os.path.join(current_dir, d))
                    return result_paths if len(result_paths) > 1 else result_paths[0]

                choice = selected[0]
                if choice == ".. (go up)":
                    current_dir = os.path.dirname(current_dir)
                    continue
                elif choice.startswith(". (select this"):
                    return current_dir
                else:
                    name = choice[2:].rstrip("/")
                    if name in dirs:
                        current_dir = os.path.join(current_dir, name)
                    else:
                        return os.path.join(current_dir, name)
            else:
                console.print(
                    f"\n[bold cyan]Current Directory:[/bold cyan] {current_dir}"
                )

                for i, item in enumerate(items):
                    if item in dirs:
                        console.print(f"{i + 1}. \U0001f4c1 {item}/")
                    else:
                        console.print(f"{i + 1}. \U0001f4c4 {item}")

                if purpose:
                    prompt = f"[yellow]Navigate by number, '..' (up), or select items (e.g., 1 or 2,3). Press '.' or 'd' to select this {purpose}, 'q' to quit.[/yellow]"
                else:
                    prompt = "[yellow]Navigate by number, '..' (up), or select items (e.g., 1 or 2,3). Press '.' or 'd' to select this directory, 'q' to quit.[/yellow]"
                choice = console.input(prompt)

                if choice and choice.lower() in ["q", "quit"]:
                    console.print("[dim]Cancelled.[/dim]")
                    return None

                if choice == "..":
                    current_dir = os.path.dirname(current_dir)
                    continue

                elif choice.lower() in [".", "d"]:
                    return current_dir

                selected_indices = [int(i.strip()) - 1 for i in choice.split(",")]
                selected_items = [items[i] for i in selected_indices]

                if len(selected_items) == 1 and selected_items[0] in dirs:
                    current_dir = os.path.join(current_dir, selected_items[0])
                else:
                    full_paths = [
                        os.path.join(current_dir, item) for item in selected_items
                    ]
                    return full_paths[0] if len(full_paths) == 1 else full_paths

        except (ValueError, IndexError):
            console.print("[bold red]Invalid choice.[/bold red]")
        except FileNotFoundError:
            console.print("[bold red]Directory not found.[/bold red]")
            current_dir = os.path.expanduser("~")


def navigate_remote_file_system(
    remote: str, purpose: Optional[str] = None, single_only: bool = False
) -> Union[List[str], str, None]:
    current_path = f"{remote}:"
    while True:
        try:
            with console.status("[dim]Loading...[/dim]"):
                output = _runner.check_output(
                    ["rclone", "lsf", current_path]
                )
            items = sorted(output.strip().split("\n")) if output.strip() else []

            if _fzf_available():
                display_items = []
                for item in items:
                    if item.endswith("/"):
                        display_items.append(f"\U0001f4c1 {item}")
                    else:
                        display_items.append(f"\U0001f4c4 {item}")
                display_items.append(".. (go up)")
                display_items.append(f". (select this {purpose or 'path'})")

                selected = _run_fzf(
                    display_items, prompt=f"\U0001f4c2 {current_path} > ", multi=True
                )
                if not selected:
                    console.print("[dim]Cancelled.[/dim]")
                    return None

                selected_items = [
                    s
                    for s in selected
                    if s not in (".. (go up)", f". (select this {purpose or 'path'})")
                ]

                if len(selected_items) > 1:
                    result_paths = []
                    dirs_to_navigate = []
                    for item in selected_items:
                        name = item[2:].rstrip("/")
                        full_path = current_path.rstrip("/") + "/" + name
                        if name.endswith("/"):
                            dirs_to_navigate.append(name)
                        else:
                            result_paths.append(full_path)
                    if dirs_to_navigate:
                        if len(dirs_to_navigate) == 1 and not result_paths:
                            current_path = (
                                current_path.rstrip("/") + "/" + dirs_to_navigate[0]
                            )
                            continue
                        else:
                            for d in dirs_to_navigate:
                                result_paths.append(current_path.rstrip("/") + "/" + d)
                    return result_paths if len(result_paths) > 1 else result_paths[0]

                choice = selected[0]
                if choice == ".. (go up)":
                    if current_path.rstrip("/") == f"{remote}:".rstrip("/"):
                        continue
                    current_path = current_path.rstrip("/")
                    current_path = current_path.rsplit("/", 1)[0] + "/"
                    if not current_path.endswith(":"):
                        current_path = current_path.rsplit("/", 1)[0] + "/"
                elif choice.startswith(". (select this"):
                    return current_path
                else:
                    name = choice[2:]
                    if name.endswith("/"):
                        current_path = current_path.rstrip("/") + "/" + name
                    else:
                        return current_path.rstrip("/") + "/" + name
            else:
                console.print(
                    f"\n[bold cyan]Current Remote Path:[/bold cyan] {current_path}"
                )

                if not any(items):
                    console.print("[dim]-- Empty --[/dim]")

                for i, item in enumerate(items):
                    if item.endswith("/"):
                        console.print(f"{i + 1}. \U0001f4c1 {item}")
                    else:
                        console.print(f"{i + 1}. \U0001f4c4 {item}")

                if purpose:
                    prompt = f"[yellow]Navigate (number), go up (..), or select items (e.g., 1,2). Press '.' or 'd' to select this {purpose}, 'q' to quit.[/yellow]"
                else:
                    prompt = "[yellow]Navigate (number), go up (..), or select items (e.g., 1,2). Press '.' or 'd' to select this path, 'q' to quit.[/yellow]"
                choice = console.input(prompt)

                if choice and choice.lower() in ["q", "quit"]:
                    console.print("[dim]Cancelled.[/dim]")
                    return None

                if choice.lower() in [".", "d"]:
                    return current_path
                elif choice == "..":
                    if current_path.strip("/") == f"{remote}:".strip("/"):
                        continue
                    current_path = os.path.dirname(current_path.rstrip("/")) + "/"
                else:
                    selected_indices = [int(i.strip()) - 1 for i in choice.split(",")]
                    selected_items = [items[i] for i in selected_indices]

                    if len(selected_items) == 1 and selected_items[0].endswith("/"):
                        current_path += selected_items[0]
                    else:
                        full_paths = [current_path + item for item in selected_items]
                        return full_paths[0] if len(full_paths) == 1 else full_paths

        except (ValueError, IndexError):
            console.print("[bold red]Invalid choice.[/bold red]")
        except subprocess.CalledProcessError:
            console.print("[bold red]Error listing remote directory.[/bold red]")
            return current_path
