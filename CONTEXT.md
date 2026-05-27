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
- 86 unit + 4 integration tests, CI pipeline (GitHub Actions)
- Ruff linting (F, E, W rules)

**Needs Work / Known Issues:**
- **Web UI auth is cosmetic** — session-state only, no server-side validation
- **`core.py` is a 1295-line god module** — handles 10+ concerns

**Recent Work:**
- 2026-05-27 — Full testing infrastructure: protocols (`ports.py`), 86 unit + 4 integration tests across all 7 modules, CI (GitHub Actions), security fixes (removed default creds, bind to localhost, sanitize logs)
- 2026-05-27 — Added ruff config, auto-fixed unused imports
- 2026-05-27 — Bumped requires-python to >=3.10, extracted duplicated helpers to `utils.py`, fixed WebUI N+1 subprocess, enabled ruff lint
- 2026-05-27 — Added `BIND_ADDRESS`, `ENABLE_XSRF_PROTECTION`, `ENABLE_CORS` config options; passwords via env vars; file permissions locked to 0o600; removed default PASSWORD fallback

**Blockers:**
- None

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
| Testing | pytest + pytest-mock + pytest-cov (86 unit + 4 integration tests) |

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
│   ├── core.py              # Core operations — serve, transfer, sync, browse
│   ├── mount.py             # FUSE mount/unmount with rc API integration
│   ├── status.py            # Status dashboard (mounts + sync pairs)
│   ├── sync_pairs.py        # Sync pair CRUD + execution (11 modes)
│   ├── ports.py             # OutputPort/CommandRunner protocols + test doubles
│   ├── utils.py             # Shared utilities, navigation, fzf, rc stats
│   ├── webui.py             # Streamlit file browser UI
│   └── webui_launcher.py    # Streamlit server launcher
├── tests/
│   ├── conftest.py          # Shared fixtures (fake_runner, test_output)
│   ├── unit/                # 86 unit tests across 7 modules
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
| Mount logic | `src/rclone_manager/mount.py` |
| Sync pairs | `src/rclone_manager/sync_pairs.py` |
| Shared utils | `src/rclone_manager/utils.py` |
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
