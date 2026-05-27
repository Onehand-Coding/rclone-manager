# Testing Infrastructure Design

## Problem

Rclone Manager has 4,077 lines of Python with zero test coverage. The codebase has testability blockers: import-time `sys.exit(1)`, global mutable cache, tight coupling with Rich console and subprocess. No CI/CD pipeline exists.

## Approach

**Interface extraction** — wrap `Console` and `subprocess` behind protocols, inject dependencies into functions. This sits between a minimal patchwork approach and a full service layer refactor. It makes tests maintainable without a rewrite and naturally paves the way for splitting `core.py`.

## Phases

### Phase 1: Testability refactor

Three targeted changes. No user-facing behavior changes.

#### 1a. `config.py` — remove import-time `sys.exit(1)`

- Lines 21-25 currently call `sys.exit(1)` at module level if `pyproject.toml` not found
- Replace with lazy `get_project_root()` function that raises `FileNotFoundError`
- CLI entry point catches the error and exits; tests can import without crashing

#### 1b. Console protocol

- New `src/rclone_manager/ports.py`: abstract `OutputPort` protocol with `print()`, `status()` context manager
- `RichOutput(wraps rich.console.Console)` — prod implementation
- `TestOutput(captures to list)` — test implementation
- Functions accept optional `console: OutputPort = None`, default to `RichOutput()`

#### 1c. Command runner protocol

- Same `ports.py`: abstract `CommandRunner` protocol with `run()`, `popen()`, `check_output()`
- `RealCommandRunner(wraps subprocess)` — prod
- `FakeCommandRunner(returns canned results)` — test
- Inject alongside Console

### Phase 2: Critical security fixes

Fix before writing tests so tests validate safe code:

- Remove default credentials (`user`/`pass` in `config.py`)
- Bind services to `127.0.0.1` by default
- Sanitize command output (don't log passwords in `ps aux`)

### Phase 3: Test infrastructure

#### File layout

```
tests/
├── conftest.py              # shared fixtures: mock_console, mock_runner
├── unit/
│   ├── test_config.py
│   ├── test_utils.py
│   ├── test_mount.py
│   ├── test_sync_pairs.py
│   ├── test_status.py
│   ├── test_cli.py
│   └── test_core.py
└── integration/
    ├── conftest.py           # sandboxed rclone config, temp dirs
    ├── test_config_integration.py
    └── test_utils_integration.py
```

#### Pytest config

In `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: marks tests that require rclone (deselect with '-m \"not integration\"')",
]
addopts = "-v --tb=short"
```

Move `[dependency-groups]` to `[project.optional-dependencies]` for pip compatibility.

#### CI workflow (`.github/workflows/ci.yml`)

- Trigger: push, pull_request
- Jobs:
  - `lint`: ruff check
  - `unit-tests`: pytest -m "not integration" with coverage
  - `integration-tests` (manual): pytest -m integration

### Phase 4: Unit tests

Written in order of independence (fewest deps first):

| Module | What to test | Mock strategy |
|--------|-------------|---------------|
| `config.py` | `build_filter_args()`, `get_filters()`, `setup_env()` | Set env vars directly, assert args |
| `utils.py` | `get_rclone_flags()`, cache logic in `list_rclone_remotes()`, `choose_from_list()`, `run_rclone_with_retry()`, `get_ip_address()` | FakeCommandRunner, assert cache hit/miss |
| `sync_pairs.py` | CRUD ops, 11 sync modes | Mock file I/O + CommandRunner |
| `mount.py` | Mount/unmount, registry | Mock subprocess + file I/O |
| `status.py` | Status display, mount detection | Mock registry + rc API |
| `cli.py` | Arg parsing, dispatch | argparse directly |
| `core.py` | Transfer/serve/browse ops | Heavy mocking initially |

Pattern: **arrange-act-assert**. No shared state between tests. Fixtures clean env vars + caches.

### Phase 5: Integration tests

- Tagged `@pytest.mark.integration`
- Use temporary rclone config with local filesystem remote
- Run separately from unit tests
- Cover: config loading from real files, rclone subprocess availability, file system navigation

### Phase 6: Coverage enforcement

Start with no minimum threshold. Raise to 70%+ once stable.

## Implementation order

1. Testability refactor (ports.py, fix config.py)
2. Security fixes
3. pyproject.toml / conftest.py / CI
4. Unit tests in dependency order
5. Integration tests
6. Coverage enforcement
