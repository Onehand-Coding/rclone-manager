# Rclone Manager

> Persistent project memory — durable knowledge only.
>
> This file is NOT a changelog, session log, TODO list, or git history.
> Git already records what changed and when. This file records what
> Git cannot: architecture, philosophy, non-goals, decisions, conventions,
> domain rules, and the current state of unfinished or partial work.
>
> Update ONLY when durable project knowledge changes (see Maintenance
> Rules at the bottom). Do not touch this file for commits, bug fixes,
> refactors, or session summaries.

---

## 1. Project Overview

**Purpose:** A Python CLI tool that simplifies rclone operations — upload/download, mount cloud storage via FUSE, serve files over HTTP/WebDAV/FTP, automate sync pairs, and browse cloud files through a Streamlit Web UI. Wraps rclone with interactive prompts, filters, and config so users never need to remember rclone flags.

**Target Users:**
- rclone users who want an interactive terminal UI instead of remembering flags
- Users who want a browser-based file browser for local + cloud storage
- Users automating remote↔remote sync with persistent sync pairs (11 modes)

**Current Milestone:** Maintenance — all 18 CLI commands functional, 262 unit + 4 integration tests, CI green.

**Current Development Focus:** Closing test-coverage gaps (stats.py ~17%, sync.py ~39%, webui.py ~25%).

**Longer-Term Direction:** Server-side validation for Web UI auth (currently session-state only).

---

## 2. Technology Stack

### Frontend
| Component | Choice |
|---|---|
| Framework | Rich (terminal UI: tables, status, prompts); Streamlit (web UI, optional `gui` extra) |
| State Management | Streamlit session_state (web); session state dicts (CLI) |
| Routing | argparse subcommands (CLI) |
| Local Storage | configs/config.ini + configs/sync-pairs.json (gitignored) |

### Backend
| Component | Choice |
|---|---|
| Framework | stdlib `argparse` — no third-party CLI frameworks |
| ORM | None |
| Validation | Manual, in-line (rclone remote validation via `rclone listremotes`) |
| Authentication | Web UI: session-state only (cosmetic); serve commands: HTTP basic auth |

### Database
| Component | Choice |
|---|---|
| Database | None — config.ini (ini), sync-pairs.json (JSON), mount registry (JSON) |
| Migrations | N/A |

### Infrastructure
| Component | Choice |
|---|---|
| Container | None |
| Reverse Proxy | None |
| Deployment | None — local tool; GitHub Actions CI (lint + unit matrix + integration) |

**Key dependencies:** `rich`, `python-dotenv` (declared, currently unused in code), `streamlit` (optional `gui` extra), `ruff` (dev), pytest + pytest-mock + pytest-cov (dev).

**Build:** Hatchling, Python 3.10+, managed with `uv`.

---

## 3. Repository Structure

```text
rclone-manager/
├── configs/
│   ├── config.ini           # User config (gitignored)
│   ├── config.ini.example   # Example config
│   └── sync-pairs.json      # Sync pair definitions (gitignored)
├── logs/
│   └── rclone_scripts.log   # Rotating log file (gitignored)
├── src/rclone_manager/      # One module per concern (see §12)
├── tests/
│   ├── conftest.py          # Shared fixtures (fake_runner, test_output)
│   ├── unit/                # 262 unit tests — mirrors src modules
│   └── integration/         # 4 integration tests (require real rclone)
├── .github/workflows/ci.yml
├── pyproject.toml
├── CONTEXT.md
└── README.md
```

---

## 4. Architecture

**Overall:** CLI-first, TUI-driven wrapper around rclone. rclone is the engine; this project adds config management, interactive selection (fzf), filters, sync-pair automation, and live transfer stats via the rclone rc API. Testability is a first-class concern: user I/O flows through the `OutputPort` protocol, command execution through the `CommandRunner` protocol, so unit tests use fakes and never invoke real rclone. The Streamlit web UI mirrors the core flows (browse local/remote, zip download, upload) but calls `subprocess` directly rather than going through the ports.

**Folder Organization:** One module per operation domain (serve, transfer, sync, mount, remote_ops, sync_pairs, stats, status), plus shared support modules (utils, fzf, navigation, remote_info, mount_helpers, ports). Tests mirror the module layout under `tests/unit/`.

**Data Flow:** user input → `cli.py` dispatch → domain module → `CommandRunner` → rclone binary (and rc API for stats/mount control) → results formatted through `OutputPort` (Rich). Config flows: config.ini → env vars → modules read via `os.environ`.

---

## 5. Non-Goals

- Not a replacement for rclone — rclone remains the engine; no reimplementation of rclone features
- No rclone install/update management
- No desktop GUI
- No multi-user / server deployment (single-user local tool)
- No Web UI uploads to remote destinations (local upload only)

---

## 6. Architecture Rules

- All interactive I/O goes through the `OutputPort` protocol (`RichOutput` in prod, fakes in tests) — never `console.*` directly
- CLI command execution goes through the `CommandRunner` protocol (`RichCommandRunner` in prod, `FakeCommandRunner` in tests)
- Unit tests never execute real rclone (FakeCommandRunner or monkeypatched `subprocess`)
- CLI framework is stdlib `argparse` — no third-party CLI frameworks
- Web UI code lives in `webui.py` only (currently bypasses the ports protocols — see §11)
- Config is loaded once into env vars by `config.py`; modules read from `os.environ`

---

## 7. Coding Conventions

**General:**
- Python 3.10+, type hints on public functions
- Docstrings on public functions; no comments unless needed
- Ruff linting: F, E, W rules with E501 ignored
- `uv run` for all commands

**Backend:**
- Modules are focused: core.py (273 lines) and utils.py (91 lines) were split from 1308/726-line monoliths — keep new code in the appropriate focused module, don't regrow monoliths

**Testing:**
- Unit tests under `tests/unit/`, one file per module, class-per-test-group pattern
- Use monkeypatch + FakeCommandRunner; never invoke real rclone in unit tests
- Integration tests require rclone and run in CI separately

---

## 8. Project Decisions

> Decisions are append-only. Never delete a decision — if no longer applicable,
> update its Status to **Superseded** or **Deprecated**.

### Ports protocols (OutputPort / CommandRunner)
**Choice:** All I/O and command execution abstracted behind protocols with prod/test doubles.
**Status:** Current
**Reason:** Made 250+ unit tests possible without invoking rclone; enables testing interactive flows.
**Alternatives Considered:** Mocking `console` and `subprocess` everywhere (brittle); abstract wrappers won.

### OutputPort.input() forwards **kwargs to Rich Prompt.ask
**Choice:** `input()` accepts and forwards prompt kwargs (e.g. `choices`, `default`).
**Status:** Current
**Reason:** `RichOutput.input()` crashed on `choices`/`default` args that `Prompt.ask` supports — the wrapper must not narrow Prompt.ask's API.
**Alternatives Considered:** Restricting CLI prompts to kwargs the wrapper knew; forwarding won.

### Single shared Rich Live for serve-remote status
**Choice:** One `with console.status(...)` on the main thread listing all served remotes; serve threads only `console.print`.
**Status:** Current
**Reason:** Rich allows only one `Live` per console — per-thread status calls crashed with `rich.errors.LiveError`.
**Alternatives Considered:** Per-thread console instances; shared-status won.

### Registry-based mount tracking
**Choice:** Mounts tracked in a registry file (JSON) with PID + rc port; unmount/stats use the rc API when available.
**Status:** Current
**Reason:** Reliable mount state across CLI invocations without relying on process listing.
**Alternatives Considered:** `/proc`/`mount` parsing (platform-specific); registry won.

### Stderr-based mount verification on Windows
**Choice:** Post-mount verification inspects rclone stderr for "Fatal error" + pre-flight WinFsp DLL check.
**Status:** Current
**Reason:** rclone opens its rc port before attempting the WinFsp FUSE mount, so "port open" falsely implied "mounted" — the earlier check showed ✅ on broken mounts.
**Alternatives Considered:** rc-port polling alone (false positives); stderr verification won.

### Web UI remote download = copy → temp → ZIP
**Choice:** Selected remote items are copied via `rclone copy` into a server temp dir (files flat, dirs into folders named after the item), zipped in memory, served as browser ZIP — mirroring the local flow. File-vs-dir detection via `rclone lsjson` (see §9).
**Status:** Current
**Reason:** Uniform handling of mixed files + folders with minimal new code; consistent with existing local ZIP download.
**Alternatives Considered:** Per-file streaming downloads (more UI complexity); direct `st.download_button` per file (loses structure).

---

## 9. Domain Knowledge

Rclone behavior facts that the code relies on (verified against rclone v1.73):

- `rclone lsjson <file>` returns the file itself as a single entry; `rclone lsjson <dir>` returns children; nonexistent path → exit code 3. Used for file-vs-dir detection (`webui._is_remote_dir`).
- `lsjson` ambiguity: a dir whose only child is a file with the same name (e.g. dir `remote:/b` containing file `b`) produces output identical to the file's own listing — `_is_remote_dir` disambiguates by checking the parent's `lsjson` listing.
- `rclone lsf`/`lsd` return exit code 0 for files too — return code alone cannot distinguish file from dir.
- `rclone copy <file> <dest>/` preserves the file's basename; `rclone copy <dir> <dest>/` copies the dir's *contents* (no wrapper dir). Dir download must target `<dest>/<name>/` explicitly to keep structure.
- `os.path.exists()` returns `False` for stale FUSE mounts (ENOTCONN on stat) — "doesn't exist" must not be taken at face value for mount paths.

---

## 10. Known Gotchas

### Rich (terminal UI)
- Only one `Live` display per console at a time — parallel `console.status()` calls crash with `rich.errors.LiveError`
- `RichOutput.input()` must forward `**kwargs` to `Prompt.ask` (e.g. `choices`, `default`) or calls crash with unexpected-keyword TypeError

### FUSE mounts
- Stale mounts: `os.path.exists()` returns False, and `os.makedirs` then raises `FileExistsError` on the leftover mount dir — wrap in try/except, then `fusermount -uz` before retrying
- Windows: rclone opens the rc port *before* attempting the WinFsp mount — port-open ≠ mounted; verify stderr for "Fatal error"

### Streamlit / Web UI
- Windows virtual shell folders (e.g. "My Documents") appear in `os.listdir()` but fail on stat — per-item try/except needed when listing
- `streamlit` is an optional extra — importing `webui.py` without the `gui` extra fails on import

**Assumptions to avoid:**
- Never assume unit tests can run real rclone — use FakeCommandRunner / monkeypatched subprocess
- Never assume `lsjson`/`lsf` behave identically on every backend (tested on local; cloud backends may differ)

---

## 11. Implementation Notes

- `core.py` was split into 5 focused modules (273 lines, down from 1308); `utils.py` into 6 (91 lines, down from 726) — new code goes in the focused modules
- `FakeCommandRunner` supports `popen()` via a `_FakePopen` wrapper
- `webui.main_app()` is a ~350-line Streamlit function — hard to unit test; the testable logic lives in module-level helpers (`list_*_directory_contents`, `download_files_as_zip`, `download_remote_files_as_zip`, `_is_remote_dir`)
- `webui.py` calls `subprocess` directly, bypassing the OutputPort/CommandRunner protocols (accepted deviation — see §6)
- `python-dotenv` is declared in pyproject.toml but not imported anywhere in `src/`

---

## 12. Repository Map

**Important Directories:**
| Directory | Purpose |
|---|---|
| `configs/` | User config.ini + sync-pairs.json (gitignored; example committed) |
| `logs/` | Rotating rclone_scripts.log (gitignored) |
| `src/rclone_manager/` | All source modules |
| `tests/unit/` | Unit tests mirroring src modules |
| `tests/integration/` | 4 integration tests (require rclone) |

**Important Files:** (entry points first)
| File | Purpose |
|---|---|
| `src/rclone_manager/cli.py:37` | CLI entry point — arg parsing, dispatch |
| `src/rclone_manager/webui.py:206` | Web UI `main_app()` — Streamlit browser |
| `src/rclone_manager/config.py:39` | Config loading, env setup, logging, filters |
| `src/rclone_manager/ports.py` | OutputPort/CommandRunner protocols + test doubles |
| `src/rclone_manager/serve.py` | Serve remote/local via http/webdav/ftp |
| `src/rclone_manager/transfer.py` | Upload/download operations |
| `src/rclone_manager/sync.py` | Remote-to-remote sync with preview |
| `src/rclone_manager/remote_ops.py` | Remote ops: ls, dedupe, space, checksum, copy-between, bisync |
| `src/rclone_manager/mount.py` | FUSE mount/unmount with rc API integration |
| `src/rclone_manager/status.py` | Status dashboard (mounts + sync pairs) |
| `src/rclone_manager/sync_pairs.py` | Sync pair CRUD + execution (11 modes) |
| `src/rclone_manager/stats.py` | Rclone rc stats + progress |
| `src/rclone_manager/fzf.py` | Fuzzy-find toggling + run |
| `src/rclone_manager/navigation.py` | Local/remote filesystem chooser |
| `src/rclone_manager/remote_info.py` | Rclone remote listing + flags |
| `src/rclone_manager/mount_helpers.py` | Mount registry + rc stats helpers |
| `src/rclone_manager/webui_launcher.py` | Streamlit server launcher |
| `src/rclone_manager/utils.py` | Shared utilities |
| `src/rclone_manager/core.py` | Config/filter management, generate-config, re-exports |
| `pyproject.toml` | Package config (Hatchling, deps, ruff, pytest) |

**Generated — never edit manually:**
| Path | Type (file/dir) | Regenerated by |
|---|---|---|
| (none) | | |

---

## 13. Development Commands

```bash
# Development
uv sync
uv run rclone-manager <command>
uv run rclone-manager generate-config
uv run rclone-manager web-ui
```

**Verification commands** — what the AI should run before claiming a task is done:

```bash
# Tests
uv run pytest tests/unit -v

# Lint
uv run ruff check src/

# Coverage
uv run pytest tests/unit -v --cov --cov-report=term-missing
```

**Common debugging:**

```bash
# Full suite including integration tests (requires rclone)
uv run pytest tests/ -v
```

---

## 14. External Services

| Service | Purpose |
|---|---|
| rclone binary | Core engine — required at runtime, must be installed separately |
| Streamlit | Web UI runtime (optional `gui` extra) |
| GitHub Actions | CI: ruff lint + unit test matrix + integration tests |

**Secrets Location:** `configs/config.ini` (gitignored) + `.env` (via python-dotenv, declared but not yet wired).

**Configuration notes:** All values come from `config.ini` DEFAULT section, exported to env vars by `config.py`:

| Variable | Purpose |
|----------|---------|
| `LOG_LEVEL` | Logging level |
| `LOG_FILE` | Log file path |
| `DEFAULT_PORT` | Port for serve commands |
| `USERNAME` / `PASSWORD` | Auth for serve + Web UI |
| `WEBUI_USERNAME` / `WEBUI_PASSWORD` | Web UI auth override (fallback to USERNAME/PASSWORD) |
| `BIND_ADDRESS` | Bind address for serve/Web UI (default: 127.0.0.1) |
| `ENABLE_XSRF_PROTECTION` | XSRF protection toggle (default: true) |
| `ENABLE_CORS` | CORS toggle (default: true, restricted to origin) |
| `INCLUDE_HIDDEN` | Show hidden files in transfers |
| `USE_FZF` | Toggle fzf fuzzy search |
| `RMAN_MOUNT_DIR` | Mount base directory |
| `RCLONE_FLAGS_*` | Per-remote-type rclone flags (from `[rclone_flags]` section) |

---

## 15. AI Collaboration Notes

**Implementation Style:**
- Prefer incremental changes over rewrites.
- Match existing code style and module organization (surgical changes).
- Minimal dependencies — justify any new dependency against the existing stack.
- Follow the ports protocols; extend them rather than bypassing (except webui.py, established deviation).

**Communication:**
- Ask before architectural decisions; present trade-offs when multiple approaches are reasonable.
- State assumptions explicitly.
- Verify rclone behavior against the real binary before relying on it (§9 facts are verified).

**Learning Preference:**
- Owner is experienced with Python; project uses uv, pytest, ruff. Favor maintainable, well-tested solutions over clever ones. TDD/verification expected: tests must pass before claiming completion.

---

## 16. Known Limitations

- Web UI auth is cosmetic — session-state only, no server-side validation
- Web UI downloads (local and remote) buffer the whole ZIP in memory (BytesIO) — large selections use significant RAM
- Web UI uploads support local destinations only; remote upload not implemented
- Web UI is single-user by design (no multi-user session isolation)
- `main_app()` (~350 lines) is not unit-testable; only extracted helpers have coverage
- Coverage gaps: stats.py (~17%), sync.py (~39%), webui.py (~25%)

---

## Maintenance Rules

> Decisions are append-only (see §8). Never delete a decision — supersede or
> deprecate it instead.

Umbrella rule: never update this file for implementation work unless it
changes durable project knowledge. (A bug fix is usually just a bug fix — but
if fixing it revealed "Flutter Web can't do X," that's a gotcha, and it belongs.)

Before touching this file, run through this checklist. If every answer is
"No," leave CONTEXT.md untouched.

- Did the architecture or a design decision change?
- Did project philosophy or a non-goal change?
- Did an architecture rule change (added, removed, or relaxed)?
- Did a coding convention change project-wide?
- Did domain knowledge get discovered or clarified?
- Did a new gotcha appear, or a wrong assumption get exposed?
- Did an implementation note change (something now mid-flight, or now resolved)?
- Did the stack, milestone, long-term direction, or external services change?
- Did a permanent limitation get added or lifted?

**Never update this file for:**
- commits
- completed tasks
- bug fixes
- refactors
- git history
- branch changes
- session summaries
- TODO lists
- transient blockers (issue tracker's job)

Git already records all of those.
