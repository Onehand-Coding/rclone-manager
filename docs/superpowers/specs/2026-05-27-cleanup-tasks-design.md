# Cleanup Tasks: Extract Duplicates, Python Version, Ruff Config, WebUI N+1

## Overview

Batch of 4 independent code-quality and performance fixes for rclone-manager, grouped into one implementation plan due to small size and overlapping file touches.

---

## Item 1: Extract Duplicated Helpers

**Problem:** `mount.py` and `status.py` each define 5 identical (or nearly identical) helper functions. These were duplicated to avoid circular imports.

**Files touched:** `mount.py`, `status.py`, `utils.py`

**Plan:**
- Move these 5 functions into `utils.py`:
  - `_is_windows()` — identical in both
  - `_get_mount_base()` — identical in both
  - `_registry_path()` — identical in both
  - `_load_registry()` — slightly different versions; merge into the more robust one (status.py's version includes a fallback path)
  - `_rc_stats()` — identical in both
- Re-export via imports in `mount.py` and `status.py` (e.g., `from ..utils import _registry_path`)
- Delete local copies from both modules
- `_load_registry` — verify the merged version works for both `mount.py` use (mount tracking) and `status.py` use (status display)

**Testing:** `test_mount.py` and `test_status.py` already test these functions via registry/mount operations. No new tests needed if imports resolve correctly.

---

## Item 2: Fix Python 3.8/3.10 Conflict

**Problem:** `pyproject.toml` advertises `>=3.8` but `mount.py` and `status.py` use `dict | None` syntax (PEP 604, requires 3.10+). CI matrix already tests 3.10/3.11/3.12 only.

**Files touched:** `pyproject.toml`

**Plan:**
- Change `requires-python = ">=3.8"` to `">=3.10"`
- No code changes needed — PEP 604 syntax is valid in 3.10+

---

## Item 3: Add Ruff Config

**Problem:** `pyproject.toml` lists ruff as a dev dependency but has no configured rules. `ruff check src/` runs but catches nothing.

**Files touched:** `pyproject.toml`

**Plan:**
- Add `[tool.ruff.lint]` section with `select = ["F", "E", "W"]`
  - **F** (pyflakes): undefined names, unused imports, syntax errors
  - **E** (pycodestyle errors): indentation, whitespace violations
  - **W** (pycodestyle warnings): minor style issues
- Run `ruff check src/`, fix all surfaced issues
- Run `ruff check tests/`, fix any issues there too
- Verify `ruff check src/ --exit-zero` passes clean

---

## Item 5: Fix WebUI N+1 Subprocess Pattern

**Problem:** `webui.py` directory listing calls `rclone ls` per file/directory entry, spawning N subprocess calls per directory view.

**Verification:** `rclone lsjson remote:path` confirmed to return a JSON array of items with `Name`, `IsDir`, `Size`, `Path`, `ModTime` fields. Non-recursive by default.

**Files touched:** `webui.py` (possibly `core.py` if listing logic lives there)

**Plan:**
- Replace per-entry `rclone ls` calls with a single `rclone lsjson <path>` call
- Parse JSON array output (one subprocess per directory, not per entry)
- Use `--files-only` and `--dirs-only` flags where filtering is needed
- Fields available: `Name`, `Path`, `Size`, `IsDir`, `ModTime`, `MimeType`
- Update any test mocks in `test_core.py` or `tests/` that simulate directory listing

---

## Testing Strategy

- Item 1: Run existing `test_mount.py` + `test_status.py` — they cover the moved functions via integration
- Item 2: Run `pytest tests/unit` — syntax already works in 3.10+
- Item 3: `ruff check src/ tests/ --exit-zero` — must pass clean
- Item 5: Update any tests that mock rclone ls calls to mock lsjson instead

