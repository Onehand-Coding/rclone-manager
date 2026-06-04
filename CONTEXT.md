# Rclone Manager

> Project memory — the single source of truth.
> REFRESH existing sections at session end — do NOT append new entries.
> Older history lives in git log, not here.

---

## 📋 Current Status

**What's Working:**
- All 18 CLI commands functional (upload, download, sync, mount, serve, etc.)
- Web UI (Streamlit) launches and browses local/remote files
- Mount/unmount with FUSE on Linux + Windows
- Sync pairs with 11 modes (local↔remote, remote↔remote)
- fzf-powered fuzzy search for interactive selection
- Live transfer stats via rclone rc API
- Global and per-pair exclude/include filters
- Registry-based mount tracking with PID + rc port
- 250 unit + 4 integration tests, CI pipeline (GitHub Actions)
- Ruff linting (F, E, W, S rules)
- core.py split into 5 focused modules (273 lines, down from 1308)
- utils.py split into 6 focused modules (99 lines, down from 726)
- FakeCommandRunner supports popen() via _FakePopen wrapper
- Stderr-based mount verification catches delayed FUSE failures on Windows
- Stale/disconnected FUSE mount cleanup on remount and during unmount finalization

**Needs Work / Known Issues:**
- **Web UI auth is cosmetic** — session-state only, no server-side validation
- **webui.py (25%) and main_app() are hard to test** — 475-line Streamlit function
- **stats.py (17%), sync.py (39%) need more tests**

**Recent Work:**
- 2026-06-04 — Fixed `FileNotFoundError` crash in Web UI local file browser when Windows virtual shell folders (e.g., "My Documents") appear in `os.listdir()` but fail on stat. Wrapped per-item filesystem calls in try/except to skip inaccessible entries. (`webui.py:80-86`)
- 2026-06-02 — Fixed `console.input("Exclude patterns", default="")` crash in `download_backup` and `upload_backup` (Rich `Prompt.ask` supports `default` but `RichOutput.input()` wrapper didn't expose it). Added `default` parameter to `OutputPort.input()` protocol and `RichOutput.input()`. (`ports.py:21,51`)
- 2026-06-02 — Fixed stale/disconnected FUSE mount handling: `os.path.exists()` returns `False` for stale mounts (ENOTCONN on stat), so cleanup was skipped and `os.makedirs` raised `FileExistsError`. Added try/except in `mount_remote` to detect stale mounts and run `fusermount -uz` before retrying. Also fixed `_finalize_unmount` to attempt lazy unmount when `os.rmdir` fails on a stale mount. (`mount.py:292-315, 555-570`)
- 2026-05-28 — Fixed false-positive mount detection on Windows (rclone opens rc port before attempting WinFsp FUSE mount, causing ✅ with broken mount). Added stderr capture thread + post-mount verification to detect "Fatal error" in rclone output. Added pre-flight WinFsp DLL check on Windows (checks System32 and Program Files\WinFsp\bin for SxS installations). (`mount.py:43-56, 191-222, 296-347`)

**Blockers:**
- None

**Next Steps:**
1. Write tests for `stats.py` (17%), `sync.py` (39%), and `webui.py` (25%) — remaining coverage gaps
2. Reduce `main_app()` in webui.py — 475-line Streamlit function makes testing hard
3. Web UI auth needs server-side validation
5. Add type hints to `webui.py`

---

## 🏗️ Project Overview

**What it is:** A Python CLI tool that simplifies rclone operations — upload/download, mount cloud storage via FUSE, serve files over HTTP/WebDAV/FTP, automate sync pairs, and browse cloud files through a Streamlit Web UI.

**Vision:** Provide an intuitive, interactive terminal UI for all common rclone workflows, eliminating the need to remember rclone flags.

---

## 🔧 Stack & Architecture

| Aspect | Value |
|--------|-------|
| Language | Python 3.10+ |
| Build System | Hatchling |
| CLI Framework | `argparse` (stdlib) |
| Terminal UI | Rich (console, tables, status, prompts) |
| Web UI | Streamlit (optional, `gui` extra) |
| Package Name | `rclone-manager-cli` |
| Dev Tooling | Ruff (F, E, W rules with E501 ignored) |
| Testing | pytest + pytest-mock + pytest-cov (250 unit + 4 integration tests) |

### Key Dependencies
| Package | Purpose |
|---------|---------|
| `rich` | Terminal UI (tables, progress, styling) |
| `python-dotenv` | `.env` file loading |
| `streamlit` (optional) | Web UI |
| `ruff` (dev) | Linting |

### Project Structure
```
rclone-manager/
├── configs/
│   ├── config.ini           # User config (gitignored)
│   ├── config.ini.example   # Example config
│   └── sync-pairs.json      # Sync pair definitions (gitignored)
├── logs/
│   └── rclone_scripts.log   # Rotating log file (gitignored)
├── src/rclone_manager/
│   ├── cli.py               # CLI entry point, arg parsing, dispatch
│   ├── config.py            # Config loading, env setup, logging, filters
│   ├── core.py              # Config/filter management, generate-config, re-exports
│   ├── serve.py             # Serve remote/local via http/webdav/ftp
│   ├── transfer.py          # Upload/download operations
│   ├── sync.py              # Remote-to-remote sync with preview
│   ├── remote_ops.py        # Remote ops: ls, dedupe, space, checksum, copy-between, bisync
│   ├── mount.py             # FUSE mount/unmount with rc API integration
│   ├── status.py            # Status dashboard (mounts + sync pairs)
│   ├── sync_pairs.py        # Sync pair CRUD + execution (11 modes)
│   ├── ports.py             # OutputPort/CommandRunner protocols + test doubles
│   ├── utils.py             # Shared utilities, navigation, fzf, rc stats
│   ├── fzf.py               # Fuzzy-find toggling + run
│   ├── navigation.py        # Local/remote filesystem chooser
│   ├── remote_info.py       # Rclone remote listing + flags
│   ├── mount_helpers.py     # Mount registry + rc stats helpers
│   ├── stats.py             # Rclone rc stats + progress
│   ├── webui.py             # Streamlit file browser UI
│   └── webui_launcher.py    # Streamlit server launcher
├── tests/
│   ├── conftest.py          # Shared fixtures (fake_runner, test_output)
│   ├── unit/                # 250 unit tests across 13 modules
│   │   ├── test_core.py
│   │   ├── test_serve.py
│   │   ├── test_transfer.py
│   │   ├── test_sync.py
│   │   ├── test_remote_ops.py
│   │   ├── test_sync_pairs.py
│   │   ├── test_mount.py
│   │   ├── test_cli.py
│   │   ├── test_utils.py
│   │   ├── test_webui.py
│   └── integration/         # 4 integration tests (require rclone)
│   ├── .github/workflows/
│   │   └── ci.yml               # Lint + unit test matrix + integration tests
├── pyproject.toml
├── CONTEXT.md
└── README.md
```

### Environment Variables (all from config.ini DEFAULT)
| Variable | Purpose |
|----------|---------|
| `LOG_LEVEL` | Logging level |
| `LOG_FILE` | Log file path |
| `DEFAULT_PORT` | Port for serve commands |
| `USERNAME` / `PASSWORD` | Auth for serve + Web UI |
| `BIND_ADDRESS` | Bind address for serve/Web UI (default: 127.0.0.1) |
| `ENABLE_XSRF_PROTECTION` | XSRF protection toggle (default: true) |
| `ENABLE_CORS` | CORS toggle (default: true, restricted to origin) |
| `INCLUDE_HIDDEN` | Show hidden files in transfers |
| `USE_FZF` | Toggle fzf fuzzy search |
| `RMAN_MOUNT_DIR` | Mount base directory |
| `RCLONE_FLAGS_*` | Per-remote-type rclone flags (from `[rclone_flags]` section) |

---

## 📁 Key Files

| Purpose | Path |
|---------|------|
| CLI entry point | `src/rclone_manager/cli.py:37` |
| Config loading | `src/rclone_manager/config.py:39` |
| Core operations | `src/rclone_manager/core.py` |
| Serve logic | `src/rclone_manager/serve.py` |
| Transfer logic | `src/rclone_manager/transfer.py` |
| Sync logic | `src/rclone_manager/sync.py` |
| Remote ops | `src/rclone_manager/remote_ops.py` |
| Mount logic | `src/rclone_manager/mount.py` |
| Sync pairs | `src/rclone_manager/sync_pairs.py` |
| Shared utils | `src/rclone_manager/utils.py` |
| Fuzzy-find | `src/rclone_manager/fzf.py` |
| Filesystem navigation | `src/rclone_manager/navigation.py` |
| Remote info | `src/rclone_manager/remote_info.py` |
| Mount helpers | `src/rclone_manager/mount_helpers.py` |
| RC stats | `src/rclone_manager/stats.py` |
| Status dashboard | `src/rclone_manager/status.py` |
| Web UI | `src/rclone_manager/webui.py` |
| Web UI launcher | `src/rclone_manager/webui_launcher.py` |
| Package config | `pyproject.toml` |

---

## ⚡ Quick Commands

```bash
# Run the CLI
uv run rclone-manager <command>

# Dev install
uv sync

# Run all unit tests
uv run pytest tests/unit -v

# Run all unit + integration tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/unit -v --cov --cov-report=term-missing

# Lint
uv run ruff check src/

# Generate default config
uv run rclone-manager generate-config

# Run web UI
uv run rclone-manager web-ui
```
