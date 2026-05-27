# Cleanup Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 independent code quality and performance issues: extract duplicated helpers, bump Python version, add ruff config, fix WebUI N+1 subprocess pattern.

**Architecture:** Each task is self-contained and touches distinct files. Task 1 (requires-python) is a one-line change. Task 2 moves 5 functions from mount.py/status.py to utils.py. Task 3 replaces per-file `rclone ls` calls with a single `rclone lsjson`. Task 4 enables ruff rules and fixes surfaced issues.

**Tech Stack:** Python 3.10+, rclone, ruff, pytest

---

### Task 1: Bump requires-python to >=3.10

**Files:**
- Modify: `pyproject.toml:10`

- [ ] **Step 1: Change requires-python**

```toml
# pyproject.toml:10
requires-python = ">=3.10"
```

- [ ] **Step 2: Run tests to verify nothing breaks**

Run: `uv run pytest tests/unit -v`
Expected: All 86 unit tests pass

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump requires-python to >=3.10

PEP 604 union syntax (dict | None) used in mount.py and status.py
requires Python 3.10+. CI matrix already tests 3.10/3.11/3.12."
```

---

### Task 2: Extract Duplicated Helpers to utils.py

**Files:**
- Modify: `src/rclone_manager/utils.py` — add 5 functions
- Modify: `src/rclone_manager/mount.py` — remove local copies, import from utils
- Modify: `src/rclone_manager/status.py` — remove local copies, import from utils

**Background:** `mount.py` and `status.py` each define their own `_is_windows()`, `_get_mount_base()`, `_registry_path()`, `_load_registry()`, `_rc_stats()`. These were duplicated to avoid circular imports. Since `utils.py` already imports nothing from either module, it's the natural home.

**Key detail — `_rc_stats` naming conflict:** `mount.py` calls it `_rc_stats(port)`, `status.py` calls it `_rc_vfs_stats(port)`, and `utils.py` already has `_get_rc_stats(port)` (which calls `core/stats` instead of `vfs/stats`). The function in mount.py and status.py calls `vfs/stats`. Keep the name `_rc_vfs_stats` in utils.py to avoid collision with `_get_rc_stats` (which does something different — `core/stats`).

- [ ] **Step 1: Add the 5 functions to utils.py**

Append these functions to `utils.py` after `_get_rc_stats` (around line 135):

```python
def _is_windows() -> bool:
    return sys.platform == "win32"


def _get_mount_base() -> str:
    return os.path.expanduser(
        os.environ.get("RMAN_MOUNT_DIR", os.environ.get("MOUNT_DIR", "~/mnt"))
    )


def _registry_path() -> str:
    return os.path.join(_get_mount_base(), ".rc_ports.json")


def _load_registry() -> dict:
    try:
        with open(_registry_path()) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in registry: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load registry: {e}")
        return {}


def _rc_vfs_stats(port: int) -> dict | None:
    """Query rclone rc vfs/stats. Returns dict or None if unavailable."""
    try:
        result = _runner.run(
            ["rclone", "rc", "vfs/stats", f"--rc-addr=127.0.0.1:{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout fetching VFS stats from port {port}")
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse VFS stats: {e}")
    except Exception as e:
        logger.warning(f"Failed to get VFS stats: {e}")
    return None
```

For `_load_registry`, both versions are identical (mount.py's version at line 115-126 and status.py's at line 42-53). The merged version above matches both.

For `_rc_vfs_stats`, `mount.py`'s `_rc_stats` (line 91-108) and `status.py`'s `_rc_vfs_stats` (line 77-93) differ in timeout (5s vs 3s). Use 5s (mount.py's version) since it's more generous.

- [ ] **Step 2: Update mount.py — add imports, remove local copies**

Replace lines 29-127 in mount.py. Remove the local definitions of `_is_windows`, `_get_mount_base`, `_registry_path`, `_load_registry`, and `_rc_stats`. Add their imports from utils.

Change the imports at the top of `mount.py` (line 12-18):

```python
from .utils import (
    choose_from_list,
    get_remote_type,
    get_rclone_flags,
    list_rclone_remotes,
    sanitize_command,
    _is_windows,
    _get_mount_base,
    _registry_path,
    _load_registry,
    _rc_vfs_stats,
)
```

Then remove lines 29-127 entirely (the section from `# ── internal helpers` to just before `_save_registry`). Keep `_save_registry`, `_remove_from_registry`, `_is_unsupported`, `_check_pending_uploads` — those are unique to mount.py.

The remaining internal helpers in mount.py after the removal are:
- `_fusermount_cmd` (line 42-44) — unique, keep
- `_is_mount_active` (line 47-53) — unique, keep
- `_find_free_port` (line 56-64) — unique, keep
- `_get_registry_entry` (line 67-72) — unique, keep
- `_unmount_via_rc` (line 75-88) — unique, keep
- `_save_registry` (line 129-133) — unique, keep
- `_remove_from_registry` (line 136-139) — unique, keep
- `_is_unsupported` (line 142-147) — unique, keep
- `_check_pending_uploads` (line 150-199) — uses `_rc_stats`, must be renamed to `_rc_vfs_stats` calls

- [ ] **Step 3: Update mount.py — rename _rc_stats call in _check_pending_uploads**

In mount.py `_check_pending_uploads` (line 155), change:
```python
stats = _rc_stats(port)
```
to:
```python
stats = _rc_vfs_stats(port)
```

And at line 184:
```python
stats = _rc_stats(port)
```
to:
```python
stats = _rc_vfs_stats(port)
```

- [ ] **Step 4: Update status.py — add imports, remove local copies**

Replace lines 16-93 in status.py. Remove the local definitions of `_is_windows`, `_get_mount_base`, `_registry_path`, `_load_registry`, and `_rc_vfs_stats`. Add their imports.

Change the imports at the top of `status.py` (line 10):

```python
from .ports import OutputPort, RichOutput
from .utils import (
    _is_windows,
    _get_mount_base,
    _registry_path,
    _load_registry,
    _rc_vfs_stats,
)
```

Then remove lines 16-93 entirely (from `# ── helpers` through `_pending_transfers`). Keep `_sync_pairs_path`, `_load_sync_pairs`, `_pending_transfers`, and `show_status`.

In `_pending_transfers` (line 96-106), change `_rc_vfs_stats` — it's already calling the same name, and the import from utils will take precedence over the removed local definition.

- [ ] **Step 5: Run tests to verify extraction works**

Run: `uv run pytest tests/unit/test_mount.py tests/unit/test_status.py -v`
Expected: All tests pass

Run: `uv run pytest tests/unit -v`
Expected: All 86 unit tests still pass

- [ ] **Step 6: Run integration tests**

Run: `uv run pytest tests/integration -v`
Expected: All 4 integration tests pass

- [ ] **Step 7: Commit**

```bash
git add src/rclone_manager/utils.py src/rclone_manager/mount.py src/rclone_manager/status.py
git commit -m "refactor: extract duplicated mount/status helpers into utils.py

Moved _is_windows, _get_mount_base, _registry_path, _load_registry,
and _rc_vfs_stats from mount.py and status.py into utils.py to
eliminate code duplication (circular import workaround).
Renamed mount.py's _rc_stats callers to _rc_vfs_stats for consistency."
```

---

### Task 3: Fix WebUI N+1 Subprocess Pattern

**Files:**
- Modify: `src/rclone_manager/webui.py:42-88`

**Background:** `list_remote_directory_contents()` in webui.py calls `rclone ls --max-depth 1 <path>` once per file to get file sizes. With N files, that's N+3 subprocess calls per directory listing. `rclone lsjson` returns `Name`, `IsDir`, `Size` fields in a single JSON array — one call replaces them all.

- [ ] **Step 1: Rewrite list_remote_directory_contents to use lsjson**

Replace the current `list_remote_directory_contents` function (lines 42-91):

```python
def list_remote_directory_contents(remote_path: str) -> list[dict]:
    """List contents of a remote directory using lsjson for single-call listing."""
    try:
        output = subprocess.check_output(
            ["rclone", "lsjson", remote_path]
        ).decode("utf-8")
        entries = json.loads(output)
    except subprocess.CalledProcessError:
        st.error(f"Error accessing remote path: {remote_path}")
        return []
    except json.JSONDecodeError:
        st.error(f"Error parsing listing for {remote_path}")
        return []

    contents = []
    for entry in entries:
        name: str = entry["Name"]
        if not st.session_state.show_hidden and name.startswith("."):
            continue
        contents.append({
            "name": name,
            "is_dir": entry["IsDir"],
            "size": f'{entry["Size"]} bytes' if not entry["IsDir"] else "-",
            "modified": entry.get("ModTime", "-"),
        })

    return sorted(contents, key=lambda x: (not x["is_dir"], x["name"]))
```

Add `import json` at the top of the file if not already present (currently webui.py imports `logging`, `os`, `time`, `subprocess`, `BytesIO`, `ZipFile`, `tempfile` — `json` is not imported).

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v --ignore=tests/integration`
Expected: All unit tests pass

Run: `uv run ruff check src/rclone_manager/webui.py --select=F,E,W`
Expected: No errors

- [ ] **Step 3: Verify the approach manually (optional)**

Run: `rclone lsjson <any-remote>:` to verify output format is as expected

- [ ] **Step 4: Commit**

```bash
git add src/rclone_manager/webui.py
git commit -m "perf: replace N+1 subprocess pattern with single lsjson call in webui

list_remote_directory_contents was calling rclone ls per file entry
to get size info. rclone lsjson returns all fields (Name, IsDir,
Size, ModTime) in one JSON array, eliminating the N+3 subprocess
spawns per directory listing."
```

---

### Task 4: Add Ruff Config and Fix Lint Issues

**Files:**
- Modify: `pyproject.toml` — add !`[tool.ruff.lint]` section
- Possibly modify: files under `src/rclone_manager/` and `tests/` that fail ruff checks

- [ ] **Step 1: Add ruff config to pyproject.toml**

Append after the `[tool.coverage.run]` section (line 44):

```toml
[tool.ruff.lint]
select = ["F", "E", "W"]
```

- [ ] **Step 2: Run ruff on src/**

Run: `uv run ruff check src/`
If clean, proceed. If issues, fix them.

Expected issues to watch for:
- `F401` — unused imports
- `F841` — unused variables
- `E501` — line too long (can be noisy; add `ignore = ["E501"]` if there are many
- `W291` — trailing whitespace

Add an `ignore` list if E501 is too noisy:
```toml
[tool.ruff.lint]
select = ["F", "E", "W"]
ignore = ["E501"]
```

- [ ] **Step 3: Run ruff on tests/**

Run: `uv run ruff check tests/`
Fix any issues.

- [ ] **Step 4: Verify no regressions**

Run: `uv run pytest tests/unit -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
# If source files changed:
git add src/ tests/
git commit -m "chore: enable ruff lint rules (F, E, W) and fix surfaced issues"
```

---

### Verification

- [ ] **Final check — all unit tests pass**

Run: `uv run pytest tests/unit -v`
Expected: All 86+ unit tests pass

- [ ] **Final check — all integration tests pass**

Run: `uv run pytest tests/integration -v`
Expected: All 4 integration tests pass

- [ ] **Final check — ruff passes clean**

Run: `uv run ruff check src/ tests/`
Expected: No errors
