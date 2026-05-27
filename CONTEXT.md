# Rclone Manager

> Project memory — the single source of truth.
> REFRESH existing sections at session end — do NOT append new entries.
> Older history lives in git log, not here.

---

## 📋 Current Status (Refresh each session)

**What's Working:**
- All 18 CLI commands functional (upload, download, sync, mount, serve, etc.)
- Web UI (Streamlit) launches and browses local/remote files
- Mount/unmount with FUSE on Linux + Windows
- Sync pairs with 11 modes (local↔remote, remote↔remote)
- fzf-powered fuzzy search for interactive selection
- Live transfer stats via rclone rc API
- Global and per-pair exclude/include filters
- Registry-based mount tracking with PID + rc port

**Needs Work / Known Issues:**
- **Web UI auth is cosmetic** — session-state only, no server-side validation; XSRF+CORS disabled
- **`core.py` is a 1295-line god module** — handles 10+ concerns

**Recent Work:**
- 2026-05-27 — Full testing infrastructure: protocols (`ports.py`), 86 unit + 4 integration tests across all 7 modules, CI (GitHub Actions), security fixes (removed default creds, bind to localhost, sanitize logs)
- 2026-05-27 — Added ruff config (`[tool.ruff.lint]` with F, E, W rules, E501 ignored), auto-fixed 5 unused imports in `src/` and 15 in `tests/`
- 2026-05-27 — Bumped requires-python to >=3.10, extracted 5 duplicated helpers from mount.py/status.py to utils.py, replaced WebUI N+1 subprocess with single lsjson call, enabled ruff lint with auto-fixes
- 2026-05-27 — Added `BIND_ADDRESS` config option (default 127.0.0.1) for serve/WebUI binding; Web UI launcher respects config instead of hardcoded 0.0.0.0

**Blockers:**
- None

---

## 🎯 Next Steps (Refresh each session)

- [x] Fix CRITICAL security issues: remove default creds, sanitize command output, bind to localhost
- [x] Extract duplicated helpers (`_is_windows`, `_get_mount_base`, `_registry_path`, `_load_registry`, `_rc_stats`) to `utils.py`
- [x] Fix Python version requirement (bump to >=3.10 or replace `dict | None` with `Optional[dict]`)
- [x] Add test infrastructure: pytest + pytest-mock + pytest-cov to dev deps, create `tests/` dir, add first unit tests
- [x] Add ruff config to `pyproject.toml`
- [x] Add CI pipeline (GitHub Actions)
- [x] Move `[dependency-groups]` to `[project.optional-dependencies]`
- [ ] Split `core.py` into `sync.py`, `browse.py`, `transfer.py`
- [x] Fix WebUI N+1 subprocess pattern in directory listing

---

## 🏗️ Project Overview (Set once at project start)

**What it is:** A Python CLI tool that simplifies rclone operations — upload/download, mount cloud storage via FUSE, serve files over HTTP/WebDAV/FTP, automate sync pairs, and browse cloud files through a Streamlit Web UI.

**Vision:** Provide an intuitive, interactive terminal UI for all common rclone workflows, eliminating the need to remember rclone flags.

**Current Focus:** Maintenance — fixing security issues, adding test coverage, improving code quality.

---

## 🔧 Stack & Architecture (Set once at project start)

### CLI Tool
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
│   ├── core.py              # God module (1295 lines) — serve, transfer, sync, browse, utils
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

### Environment Variables
| Variable | Source | Purpose |
|----------|--------|---------|
| `LOG_LEVEL` | config.ini DEFAULT | Logging level |
| `LOG_FILE` | config.ini DEFAULT | Log file path |
| `DEFAULT_PORT` | config.ini DEFAULT | Port for serve commands |
| `USERNAME` / `PASSWORD` | config.ini DEFAULT | Auth for serve + Web UI |
| `INCLUDE_HIDDEN` | config.ini DEFAULT | Show hidden files in transfers |
| `USE_FZF` | config.ini DEFAULT | Toggle fzf fuzzy search |
| `RMAN_MOUNT_DIR` | config.ini DEFAULT | Mount base directory |
| `RCLONE_FLAGS_*` | config.ini rclone_flags | Per-remote-type rclone flags |

---

## 📁 Key Files (Set once at project start)

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

## ⚡ Quick Commands (Set once at project start)

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

---

## 🔒 Audit Summary (2026-05-27)

### Security (16 findings — 5 CRITICAL, 6 HIGH, 4 MEDIUM, 1 LOW)

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 5 | Plaintext password in config.ini + source defaults, password logged to disk, XSRF+CORS disabled, password on CLI args |
| HIGH | 6 | Client-side-only Web UI auth, services on 0.0.0.0, no rate limiting, path traversal in upload |
| MEDIUM | 4 | Weak 6-digit password, world-readable config files, unsecured registry |
| LOW | 1 | No security headers |

**2026-05-27 fixes:**
- Removed default creds from `config.py` DEFAULTS
- All serve commands bind to `127.0.0.1`
- Command logging sanitized via `sanitize_command()` in `utils.py`

### Code Quality (40 findings — 11 HIGH, 15 MEDIUM, 14 LOW)
- `core.py` god module (1295 lines, 10+ responsibilities)
- 4 overly complex functions (171-186 lines each) with duplicated fzf/non-fzf branches
- stderr crash in `_serve_remote_thread` (missing `capture_output=True`)
- Dead parameter `overwrite` in `check_remote()`
- `list_rclone_remotes` duplicated in `webui.py` without caching

### Performance / DevOps (19 findings — 7 HIGH, 7 MEDIUM, 5 LOW)
- `sync_remotes` preview: 3 redundant `rclone check` calls
- `run_rclone_with_retry()` defined but never called
- Stats polling hardcoded to 2s interval
- No CI/CD pipeline at all
- `[dependency-groups]` is uv-specific (breaks pip)
- Port scanning brute-force (5572→5700)

### Testing (resolved — see "Recent Work")
- 86 unit + 4 integration tests across all 7 modules
- Testability refactors: `ports.py` protocols, lazy `get_project_root()`, swappable console/runner
- Security fixes applied: no default creds, bind to localhost, sanitized logging
- CI pipeline (GitHub Actions) with lint + coverage matrix
