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
- 127 unit + 4 integration tests, CI pipeline (GitHub Actions)
- Ruff linting (F, E, W, S rules)
- core.py split into 5 focused modules (273 lines, down from 1308)
- utils.py split into 6 focused modules (99 lines, down from 726)
- FakeCommandRunner supports popen() via _FakePopen wrapper

**Needs Work / Known Issues:**
- **Web UI auth is cosmetic** — session-state only, no server-side validation
- **mount.py (39%), remote_ops.py (34%), utils.py (21%) need more tests**

**Recent Work:**
- 2026-05-27 — Refactored utils.py into fzf.py, navigation.py, remote_info.py, mount_helpers.py, stats.py (726→99 lines). Added WEBUI_USERNAME/WEBUI_PASSWORD to DEFAULTS. Fixed silently-swallowed OSErrors with logger.warning. Extracted merge_filter_args helper for filter merging. Added 18 new tests (127 total), 17 focused on mount.py coverage. Added _FakePopen to FakeCommandRunner for popen() support.

**Blockers:**
- None

**Next Steps:**
1. Write tests for `remote_ops.py` (34% → 60%)
2. Write tests for `sync_pairs.py` (29% → 60%)
3. Write tests for `webui.py` (0% → meaningful coverage)
4. Add integration tests to CI pipeline
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
| Testing | pytest + pytest-mock + pytest-cov (127 unit + 4 integration tests) |

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
│   ├── unit/                # 127 unit tests across 10 modules
│   │   ├── test_core.py
│   │   ├── test_serve.py
│   │   ├── test_transfer.py
│   │   ├── test_sync.py
│   │   └── ...
│   └── integration/         # 4 integration tests (require rclone)
├── .github/workflows/
│   └── ci.yml               # Lint + unit test matrix (3.10, 3.11, 3.12)
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
