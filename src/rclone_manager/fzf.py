import os
import shutil
import logging
from typing import List

from .ports import CommandRunner, OutputPort, RealCommandRunner, RichOutput

logger = logging.getLogger(__name__)
console: OutputPort = RichOutput()
_runner: CommandRunner = RealCommandRunner()


def _toggle_fzf(action: str) -> None:
    from .config import get_project_root
    from configparser import ConfigParser

    config_path = os.path.join(get_project_root(), "configs", "config.ini")

    if not os.path.exists(config_path):
        console.print(
            "[bold red]config.ini not found. Run 'rman generate-config' first.[/bold red]"
        )
        return

    config = ConfigParser()
    config.read(config_path)

    if action == "status":
        enabled = os.environ.get("USE_FZF", "true").lower() != "false"
        has_fzf = shutil.which("fzf") is not None
        console.print("\n[bold]Fuzzy Search Status[/bold]")
        console.print(
            f"  Config  : {'[green]ON[/green]' if enabled else '[yellow]OFF[/yellow]'}"
        )
        console.print(
            f"  fzf     : {'[green]installed[/green]' if has_fzf else '[red]not found[/red]'}"
        )
        console.print(
            f"  Active  : {'[green]yes[/green]' if _fzf_available() else '[red]no[/red]'}"
        )
        return

    new_value = "true" if action == "on" else "false"

    if "DEFAULT" not in config:
        config["DEFAULT"] = {}
    config["DEFAULT"]["USE_FZF"] = new_value

    with open(config_path, "w") as f:
        config.write(f)

    label = "[green]ON[/green]" if action == "on" else "[yellow]OFF[/yellow]"
    console.print(f"\n[bold]Fuzzy search set to {label}.[/bold]")
    console.print("[dim]Restart the app for changes to take effect.[/dim]")


def _fzf_available() -> bool:
    if os.environ.get("USE_FZF", "true").lower() == "false":
        return False
    return shutil.which("fzf") is not None


def _run_fzf(items: List[str], prompt: str = "", multi: bool = False) -> List[str]:
    fzf_cmd = ["fzf", "--height=40%", "--layout=reverse", "--border=rounded"]
    if prompt:
        fzf_cmd.extend(["--prompt", f"{prompt} "])
    if multi:
        fzf_cmd.append("-m")

    result = _runner.run(
        fzf_cmd, input="\n".join(items), capture_output=True, text=True
    )

    if result.returncode not in (0, 1):
        return []

    return [line for line in result.stdout.strip().split("\n") if line]
