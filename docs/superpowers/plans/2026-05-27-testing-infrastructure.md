# Testing Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add test infrastructure and test coverage (unit + integration) with testability refactors and security fixes as prerequisites.

**Architecture:** Extract `OutputPort` and `CommandRunner` protocols into a new `ports.py`, make module-level console/runner swappable, fix import-time side effects in `config.py`, then write tests module-by-module.

**Tech Stack:** Python 3.8+, pytest 7.4+, pytest-mock, pytest-cov, ruff

---

## File Structure

**Created:**
- `src/rclone_manager/ports.py` — OutputPort, CommandRunner protocols, test doubles
- `tests/__init__.py`
- `tests/conftest.py` — shared fixtures (mock_console, mock_runner)
- `tests/unit/__init__.py`
- `tests/unit/test_config.py`
- `tests/unit/test_utils.py`
- `tests/unit/test_sync_pairs.py`
- `tests/unit/test_mount.py`
- `tests/unit/test_status.py`
- `tests/unit/test_cli.py`
- `tests/unit/test_core.py`
- `tests/integration/__init__.py`
- `tests/integration/conftest.py` — sandboxed rclone config, temp dirs
- `tests/integration/test_config_integration.py`
- `.github/workflows/ci.yml` — CI pipeline

**Modified:**
- `src/rclone_manager/config.py` — lazy `get_project_root()`, remove import-time `sys.exit(1)`
- `src/rclone_manager/utils.py` — use `OutputPort` protocol, make console swappable
- `src/rclone_manager/cli.py` — handle `PROJECT_ROOT` error at entry point
- `src/rclone_manager/core.py` — use `OutputPort`, make console swappable
- `src/rclone_manager/mount.py` — use `OutputPort`, make console swappable
- `src/rclone_manager/status.py` — use `OutputPort`, make console swappable
- `src/rclone_manager/sync_pairs.py` — use `OutputPort`, make console swappable
- `pyproject.toml` — pytest config, move `[dependency-groups]` to `[project.optional-dependencies]`

---

### Task 1: Create `ports.py` with OutputPort + CommandRunner protocols

**Files:**
- Create: `src/rclone_manager/ports.py`

- [ ] **Step 1: Write the file**

```python
from __future__ import annotations

import subprocess
from typing import Any, ContextManager, Iterator, List, Optional, Protocol, Tuple


class CommandResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class OutputPort(Protocol):
    def print(self, *values: Any, style: str = "") -> None: ...

    def status(self, message: str = "") -> ContextManager[Any]: ...

    def input(self, prompt: str = "") -> str: ...


class CommandRunner(Protocol):
    def run(
        self, command: List[str], **kwargs: Any
    ) -> CommandResult: ...

    def popen(
        self, command: List[str], **kwargs: Any
    ) -> subprocess.Popen: ...

    def check_output(self, command: List[str], **kwargs: Any) -> str: ...


class RichOutput:
    def __init__(self) -> None:
        from rich.console import Console

        self._console = Console()

    def print(self, *values: Any, style: str = "") -> None:
        self._console.print(*values)

    def status(self, message: str = "") -> ContextManager[Any]:
        return self._console.status(message)

    def input(self, prompt: str = "") -> str:
        from rich.prompt import Prompt
        return Prompt.ask(prompt)


class RealCommandRunner:
    def run(
        self, command: List[str], **kwargs: Any
    ) -> CommandResult:
        result = subprocess.run(command, **kwargs)
        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout if isinstance(result.stdout, str) else "",
            stderr=result.stderr if isinstance(result.stderr, str) else "",
        )

    def popen(self, command: List[str], **kwargs: Any) -> subprocess.Popen:
        return subprocess.Popen(command, **kwargs)

    def check_output(self, command: List[str], **kwargs: Any) -> str:
        return subprocess.check_output(command, **kwargs).decode("utf-8")


class TestOutput:
    def __init__(self) -> None:
        self.messages: List[str] = []
        self.input_responses: List[str] = []

    def print(self, *values: Any, style: str = "") -> None:
        self.messages.append(" ".join(str(v) for v in values))

    def status(self, message: str = "") -> ContextManager[Any]:
        class FakeStatus:
            def update(self, text: str = "") -> None:
                pass

            def __enter__(self) -> "FakeStatus":
                return self

            def __exit__(self, *args: Any) -> None:
                pass

        return FakeStatus()

    def add_input_response(self, value: str) -> None:
        self.input_responses.append(value)

    def input(self, prompt: str = "") -> str:
        if self.input_responses:
            return self.input_responses.pop(0)
        return ""


class FakeCommandRunner:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.commands: List[List[str]] = []
        self.responses: List[CommandResult] = []

    def add_response(self, result: CommandResult) -> None:
        self.responses.append(result)

    def run(self, command: List[str], **kwargs: Any) -> CommandResult:
        self.commands.append(command)
        if self.responses:
            return self.responses.pop(0)
        return CommandResult(returncode=0, stdout="")

    def popen(self, command: List[str], **kwargs: Any) -> subprocess.Popen:
        self.commands.append(command)
        raise NotImplementedError("FakeCommandRunner.popen not implemented — mock it")

    def check_output(self, command: List[str], **kwargs: Any) -> str:
        self.commands.append(command)
        if self.responses:
            return self.responses.pop(0).stdout
        return ""
```

- [ ] **Step 2: Commit**

```
git add src/rclone_manager/ports.py
git commit -m "feat: add OutputPort and CommandRunner protocols for testability"
```

---

### Task 2: Fix `config.py` — remove import-time `sys.exit(1)`

**Files:**
- Modify: `src/rclone_manager/config.py:11-25`

- [ ] **Step 1: Replace module-level try/except with lazy function**

Change lines 11-25 from:
```python
def find_project_root(marker: str = "pyproject.toml") -> Path:
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
```

To:
```python
def find_project_root(marker: str = "pyproject.toml") -> Path:
    current_path = Path(__file__).resolve()
    while current_path != current_path.parent:
        if (current_path / marker).exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError(f"Project root marker '{marker}' not found.")

def get_project_root() -> Path:
    try:
        return find_project_root()
    except FileNotFoundError as e:
        raise FileNotFoundError(str(e)) from e
```

- [ ] **Step 2: Update `cli.py` to handle the error at entry point**

Change `cli.py:6-41` from:
```python
from .config import PROJECT_ROOT
...
def main():
    setup_env(PROJECT_ROOT)
```

To:
```python
from .config import get_project_root
...
def main():
    try:
        root = get_project_root()
    except FileNotFoundError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)
    setup_env(root)
```

- [ ] **Step 3: Update all imports of `PROJECT_ROOT` from `config`**

Search for `from .config import PROJECT_ROOT` across all files:

`cli.py:6` → already covered above.
`core.py:11` → `from .config import get_project_root, setup_env` and replace `PROJECT_ROOT` with a module-level call.
`utils.py:23` → Change to use get_project_root() inside the function.

Let me check what other files import PROJECT_ROOT:
    - `core.py:11`
    - `cli.py:6`
    - `utils.py` has `from .config import PROJECT_ROOT` inside function `_toggle_fzf()`

Update each one:
- `core.py` — add `from .config import get_project_root`, replace `PROJECT_ROOT` references with `get_project_root()`
- `utils.py` — replace `from .config import PROJECT_ROOT` with `from .config import get_project_root` and use `get_project_root()` inside `_toggle_fzf()`

- [ ] **Step 4: Commit**

```
git add src/rclone_manager/config.py src/rclone_manager/cli.py src/rclone_manager/core.py src/rclone_manager/utils.py
git commit -m "refactor: make PROJECT_ROOT lazy to allow test imports"
```

---

### Task 3: Make console swappable in all modules

**Files:**
- Modify: `src/rclone_manager/utils.py`
- Modify: `src/rclone_manager/core.py`
- Modify: `src/rclone_manager/mount.py`
- Modify: `src/rclone_manager/status.py`
- Modify: `src/rclone_manager/sync_pairs.py`

- [ ] **Step 1: Update `utils.py`**

Change:
```python
from rich.console import Console
...
console = Console()
```

To:
```python
from .ports import OutputPort, RichOutput
...
console: OutputPort = RichOutput()
```

This keeps all existing `console.print(...)` and `console.status(...)` calls working, but now they go through the protocol. Tests can patch `rclone_manager.utils.console` with a `TestOutput`.

The `OutputPort` protocol (defined in Task 1) already includes `input()`. Update `utils.py` to use `console.input()` for prompts. In `choose_from_list`, replace:
```python
choice_str = Prompt.ask(f"[yellow]{message}[/yellow]")
```
with:
```python
choice_str = console.input(f"[yellow]{message}[/yellow]")
```

Same for `navigate_local_file_system` and `navigate_remote_file_system`.

- [ ] **Step 2: Update `core.py`**

Change:
```python
from rich.console import Console
...
console = Console()
```

To:
```python
from .ports import OutputPort, RichOutput
...
console: OutputPort = RichOutput()
```

Replace `Prompt.ask(...)` calls with `console.input(...)`. Search for all `.ask(` calls in the file.

- [ ] **Step 3: Update `mount.py`**

Change `console = Console()` → `console: OutputPort = RichOutput()`. Check if `Prompt.ask` is used in the file; if so, replace with `console.input()`.

- [ ] **Step 4: Update `status.py`**

Change `console = Console()` → `console: OutputPort = RichOutput()`. This module likely only uses `console.print()` and `Table()`, so no `Prompt.ask` changes needed.

- [ ] **Step 5: Update `sync_pairs.py`**

Change `console = Console()` → `console: OutputPort = RichOutput()`. Replace any `Prompt.ask(...)` calls with `console.input(...)`.

- [ ] **Step 6: Commit**

```
git add src/rclone_manager/utils.py src/rclone_manager/core.py src/rclone_manager/mount.py src/rclone_manager/status.py src/rclone_manager/sync_pairs.py
git commit -m "refactor: use OutputPort protocol for console across all modules"
```

---

### Task 4: Make subprocess calls testable via CommandRunner

**Files:**
- Modify: `src/rclone_manager/utils.py`
- Modify: `src/rclone_manager/core.py`
- Modify: `src/rclone_manager/mount.py`
- Modify: `src/rclone_manager/sync_pairs.py`

- [ ] **Step 1: Add runner to `utils.py`**

```python
from .ports import CommandRunner, RealCommandRunner
...
_runner: CommandRunner = RealCommandRunner()
```

Replace `subprocess.run(...)` calls with `_runner.run(...)`, `subprocess.check_output(...)` with `_runner.check_output(...)`, `subprocess.Popen(...)` with `_runner.popen(...)`.

Key functions to update:
- `_run_fzf()` — `subprocess.run()` → `_runner.run()`
- `_run_rclone_with_stats()` — `subprocess.Popen()` → `_runner.popen()`
- `list_rclone_remotes()` — `subprocess.check_output()` → `_runner.check_output()`
- `get_remote_type()` — `subprocess.check_output()` → `_runner.check_output()`
- `run_rclone_with_retry()` — `subprocess.run()` → `_runner.run()`
- `navigate_remote_file_system()` — `subprocess.check_output()` → `_runner.check_output()`

- [ ] **Step 2: Update `core.py`**

Replace `subprocess.run()`/`subprocess.check_output()` calls with `_runner.run()`/`_runner.check_output()`.

- [ ] **Step 3: Update `mount.py`**

Same pattern.

- [ ] **Step 4: Update `sync_pairs.py`**

Same pattern.

- [ ] **Step 5: Commit**

```
git add src/rclone_manager/utils.py src/rclone_manager/core.py src/rclone_manager/mount.py src/rclone_manager/sync_pairs.py
git commit -m "refactor: use CommandRunner protocol for subprocess calls"
```

---

### Task 5: Configure pytest and create conftest.py

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`

- [ ] **Step 1: Update `pyproject.toml`**

Add pytest config:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: marks tests that require rclone (deselect with '-m \"not integration\"')",
]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["src"]
```

Move `[dependency-groups]` to `[project.optional-dependencies]`:
```toml
[project.optional-dependencies]
dev = [
    "ruff>=0.15.9",
    "pytest>=7.4",
    "pytest-mock>=3.12",
    "pytest-cov>=4.1",
]
gui = ["streamlit"]
```

Remove the `[dependency-groups]` section (it conflicts with pip's standard format).

- [ ] **Step 2: Create `tests/conftest.py`**

```python
from typing import List
import pytest
from rclone_manager.ports import FakeCommandRunner, TestOutput


@pytest.fixture
def fake_runner() -> FakeCommandRunner:
    return FakeCommandRunner()


@pytest.fixture
def test_output() -> TestOutput:
    return TestOutput()
```

- [ ] **Step 3: Create empty `__init__.py` files**

```python
# tests/__init__.py — empty
# tests/unit/__init__.py — empty
# tests/integration/__init__.py — empty
```

- [ ] **Step 4: Verify pytest can import**

Run:
```
uv run pytest --collect-only
```
Expected: "no tests collected" (no errors from the import-time fix).

- [ ] **Step 5: Commit**

```
git add pyproject.toml tests/
git commit -m "chore: configure pytest and create test directories"
```

---

### Task 6: Write unit tests for `config.py`

**Files:**
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write and run tests**

```python
import os
from pathlib import Path
import pytest
from rclone_manager.config import build_filter_args, get_filters


class TestBuildFilterArgs:
    def test_empty_filters(self):
        result = build_filter_args({"exclude": [], "include": []})
        # By default, hidden files are excluded
        assert "--exclude" in result

    def test_hidden_included_when_env_set(self, monkeypatch):
        monkeypatch.setenv("INCLUDE_HIDDEN", "true")
        result = build_filter_args({"exclude": [], "include": []})
        assert "--exclude" not in result

    def test_exclude_patterns(self):
        filters = {"exclude": ["*.log", "tmp/"], "include": []}
        result = build_filter_args(filters)
        assert "--exclude" in result
        assert "*.log" in result
        assert "tmp/" in result

    def test_include_patterns(self):
        filters = {"exclude": [], "include": ["*.py", "src/"]}
        result = build_filter_args(filters)
        assert "--include" in result
        assert "*.py" in result

    def test_exclude_and_include(self):
        filters = {"exclude": ["*.log"], "include": ["*.py"]}
        result = build_filter_args(filters)
        assert result.count("--exclude") > 0
        assert result.count("--include") > 0


class TestGetFilters:
    def test_returns_empty_when_config_missing(self, tmp_path):
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"exclude": [], "include": []}

    def test_parses_exclude_patterns(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "config.ini"
        config_file.write_text("[filters]\nexclude = *.log\n  tmp/\ninclude = ")
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"exclude": ["*.log", "tmp/"], "include": []}

    def test_parses_include_patterns(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "config.ini"
        config_file.write_text("[filters]\ninclude = *.py\n  src/\nexclude = ")
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"include": ["*.py", "src/"], "exclude": []}

    def test_parses_both_patterns(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "config.ini"
        config_file.write_text("[filters]\nexclude = *.log\ninclude = *.py")
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"exclude": ["*.log"], "include": ["*.py"]}

    def test_missing_filters_section(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "config.ini"
        config_file.write_text("[DEFAULT]\nkey = value\n")
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"exclude": [], "include": []}
```

- [ ] **Step 2: Run tests**

```
uv run pytest tests/unit/test_config.py -v
```
Expected: all 8 tests pass.

- [ ] **Step 3: Commit**

```
git add tests/unit/test_config.py
git commit -m "test: add unit tests for config.py (build_filter_args, get_filters)"
```

---

### Task 7: Write unit tests for `utils.py` (stateless functions)

**Files:**
- Create: `tests/unit/test_utils.py`

- [ ] **Step 1: Write tests for `get_rclone_flags`**

```python
import os
import pytest
from rclone_manager.utils import get_rclone_flags


class TestGetRcloneFlags:
    def test_empty_when_no_type(self):
        assert get_rclone_flags("") == []

    def test_empty_when_no_env(self):
        assert get_rclone_flags("drive") == []

    def test_returns_flags_from_env(self, monkeypatch):
        monkeypatch.setenv("RCLONE_FLAGS_DRIVE", "--drive-shared-with-me")
        result = get_rclone_flags("drive")
        assert result == ["--drive-shared-with-me"]

    def test_splits_flags(self, monkeypatch):
        monkeypatch.setenv("RCLONE_FLAGS_DRIVE", "--flag1 --flag2 --flag3")
        result = get_rclone_flags("drive")
        assert result == ["--flag1", "--flag2", "--flag3"]
```

- [ ] **Step 2: Write tests for `get_ip_address`**

```python
class TestGetIpAddress:
    def test_returns_string(self):
        from rclone_manager.utils import get_ip_address
        result = get_ip_address()
        assert isinstance(result, str)
        assert len(result) > 0
```

- [ ] **Step 3: Write tests for `run_rclone_with_retry`**

```python
from rclone_manager.ports import CommandResult


class TestRunRcloneWithRetry:
    def test_success_on_first_attempt(self, monkeypatch):
        from rclone_manager.utils import run_rclone_with_retry
        import subprocess
        calls = []

        def fake_run(*args, **kwargs):
            calls.append(1)
            class FakeResult:
                returncode = 0
                stdout = "ok"
                stderr = ""
            return FakeResult()

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = run_rclone_with_retry(["ls"])
        assert result.returncode == 0
        assert len(calls) == 1
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/unit/test_utils.py -v
```

- [ ] **Step 5: Commit**

```
git add tests/unit/test_utils.py
git commit -m "test: add unit tests for utils.py (get_rclone_flags, get_ip_address, run_rclone_with_retry)"
```

---

### Task 8: Security fixes

**Files:**
- Modify: `src/rclone_manager/config.py`
- Modify: `src/rclone_manager/core.py`

- [ ] **Step 1: Remove default credentials**

In `config.py`, change:
```python
DEFAULTS = {
    ...
    "USERNAME": "user",
    "PASSWORD": "pass",
    ...
}
```

To require explicit config — remove USERNAME and PASSWORD from DEFAULTS:
```python
DEFAULTS = {
    "LOG_LEVEL": "INFO",
    "LOG_FILE": "logs/rclone_scripts.log",
    "DEFAULT_PORT": "8080",
    "INCLUDE_HIDDEN": "false",
    "USE_FZF": "true",
}
```

- [ ] **Step 2: Bind services to localhost**

In `core.py`, find `_serve_remote_thread` and change the serve command to include `--addr 127.0.0.1:{port}` instead of `0.0.0.0:{port}` or no address binding.

- [ ] **Step 3: Sanitize command logging**

In `core.py`, find all places where commands are logged (e.g., `logger.info(f"Running: {' '.join(cmd)}")`). Replace full command logging with redacted versions that strip `--pass` and similar sensitive flag values.

Example fix:
```python
# Before
logger.info(f"Running: {' '.join(cmd)}")

# After
_safe_cmd = [
    f"***{arg[-4:]}" if arg.startswith("--pass") or "password" in arg.lower() else arg
    for arg in cmd
]
logger.info(f"Running: {' '.join(_safe_cmd)}")
```

Search `core.py`, `mount.py`, and `utils.py` for `logger.info` or `logger.debug` containing command variables.

- [ ] **Step 4: Commit**

```
git add src/rclone_manager/config.py src/rclone_manager/core.py
git commit -m "fix: remove default credentials, bind to localhost, sanitize logs"
```

---

### Task 9: CI pipeline

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CI workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          python-version: "3.10"
      - run: uv sync
      - run: uv run ruff check src/

  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          python-version: ${{ matrix.python-version }}
      - run: uv sync
      - run: uv run pytest tests/unit -v --cov --cov-report=term-missing
```

- [ ] **Step 2: Commit**

```
git add .github/workflows/ci.yml
git commit -m "ci: add lint and unit test pipeline"
```

---

### Task 10: Write remaining unit tests

Each module gets its own test file. Follow the patterns established in Tasks 6-7.

- [ ] **Step 1: `tests/unit/test_sync_pairs.py`**

Test the CRUD operations (add, list, remove, run) for sync pairs. Mock file I/O for the JSON sync-pairs file and mock `CommandRunner` for rclone calls. Test all key modes: local-to-remote, remote-to-remote, bisync, etc.

```python
class TestSyncPairsList:
    def test_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rclone_manager.sync_pairs.PROJECT_ROOT", tmp_path)
        from rclone_manager.sync_pairs import sync_pairs_list
        result = sync_pairs_list()
        assert result == []

    def test_parses_existing_pairs(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rclone_manager.sync_pairs.PROJECT_ROOT", tmp_path)
        pairs_file = tmp_path / "configs" / "sync-pairs.json"
        pairs_file.parent.mkdir(parents=True)
        pairs_file.write_text('[{"name": "backup", "source": "local:/data", "dest": "remote:backup", "mode": "sync"}]')
        from rclone_manager.sync_pairs import sync_pairs_list
        result = sync_pairs_list()
        assert len(result) == 1
        assert result[0]["name"] == "backup"
```

- [ ] **Step 2: `tests/unit/test_cli.py`**

Test argument parsing — that each subcommand dispatches correctly and that missing args produce the right error.

```python
class TestArgParsing:
    def test_generate_config_command(self):
        import argparse
        from rclone_manager.cli import main
        # Simulate argparse directly
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("generate-config")
        args = parser.parse_args(["generate-config"])
        assert args.command == "generate-config"
```

- [ ] **Step 3: `tests/unit/test_mount.py`**

Test mount/unmount logic by mocking subprocess calls. Test edge cases: already mounted, invalid remote, port conflicts.

```python
class TestMountRemote:
    def test_mount_calls_rclone(self, fake_runner, monkeypatch):
        monkeypatch.setattr("rclone_manager.mount._runner", fake_runner)
        fake_runner.add_response(CommandResult(returncode=0))
        from rclone_manager.mount import mount_remote
        # Implementation depends on how mount_remote reads input;
        # this is a template that will be filled in during implementation
```

- [ ] **Step 4: `tests/unit/test_status.py`**, `tests/unit/test_core.py`

Same approach: mock subprocess + console, test edge cases. Core patterns:
- Use `monkeypatch.setattr("module.console", test_output)` to capture output
- Use `fake_runner` (from conftest) to mock subprocess calls
- Test error paths (rclone not found, timeout, invalid remote)

---

### Task 11: Integration tests

**Files:**
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_config_integration.py`

- [ ] **Step 1: Create integration conftest**

```python
import os
import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def sandbox_rclone_config(tmp_path):
    """Create a temporary rclone config with a local filesystem remote."""
    config_path = tmp_path / "rclone.conf"
    remote_dir = tmp_path / "testdata"
    remote_dir.mkdir()

    (remote_dir / "file1.txt").write_text("hello")
    (remote_dir / "subdir").mkdir()
    (remote_dir / "subdir" / "file2.txt").write_text("world")

    config_path.write_text(f"[test-local]\ntype = local\n")
    return str(config_path)
```

- [ ] **Step 2: Write integration tests**

```python
import subprocess
import pytest


pytestmark = pytest.mark.integration


class TestRcloneAvailable:
    def test_rclone_installed(self):
        result = subprocess.run(["rclone", "version"], capture_output=True, text=True)
        assert result.returncode == 0


class TestConfigLoading:
    def test_setup_env_from_config(self, sandbox_rclone_config, monkeypatch):
        monkeypatch.setenv("RCLONE_CONFIG", sandbox_rclone_config)
        from rclone_manager.config import setup_env
        setup_env("/tmp")
        # Verify rclone can list the test remote
        result = subprocess.run(
            ["rclone", "lsf", "test-local:", f"--config={sandbox_rclone_config}"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "file1.txt" in result.stdout
```

- [ ] **Step 3: Run integration tests**

```
uv run pytest tests/integration -v -m integration
```

- [ ] **Step 4: Commit**

```
git add tests/integration/
git commit -m "test: add integration test scaffolding and config tests"
```

---

### Task 12: Update CONTEXT.md

**Files:**
- Modify: `CONTEXT.md`

- [ ] **Step 1: Update status section**

Mark test coverage as started, add link to spec and plan.

- [ ] **Step 2: Commit**

```
git add CONTEXT.md
git commit -m "docs: update CONTEXT.md with testing infrastructure progress"
```
