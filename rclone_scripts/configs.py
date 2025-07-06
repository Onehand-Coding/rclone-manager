import sys
from pathlib import Path

def find_project_root(marker: str = "pyproject.toml") -> Path:
    """Dynamically finds the project root by searching upwards for a marker file."""
    current_path = Path(__file__).resolve()
    while current_path != current_path.parent:
        if (current_path / marker).exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError(f"Project root marker '{marker}' not found.")

try:
    PROJECT_ROOT = find_project_root()
except FileNotFoundError as e:
    print(f"FATAL ERROR: Could not determine project root. {e}", file=sys.stderr)
    sys.exit(1)
