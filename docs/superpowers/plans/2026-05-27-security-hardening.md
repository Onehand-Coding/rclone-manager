# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 5 remaining CRITICAL/HIGH security issues from the audit with surgical, low-risk changes.

**Architecture:** Config-driven approach — security settings live in `config.ini` with secure defaults, read as env vars at runtime. Password handling moved from CLI args to environment variables. File permissions locked to owner-only.

**Tech Stack:** Python 3.10+, rclone, Streamlit

---

### Task 1: Enable XSRF/CORS protection (config-driven)

**Files:**
- Modify: `src/rclone_manager/config.py:27-34`
- Modify: `src/rclone_manager/webui_launcher.py:12-30`
- Modify: `configs/config.ini.example:7-14`

**Rationale:** Currently both protections are hardcoded `false`. Add config options with `true` defaults so users can disable them only when needed (e.g., LAN access from non-browser clients).

- [ ] **Step 1: Add ENABLE_XSRF_PROTECTION and ENABLE_CORS to DEFAULTS**

In `src/rclone_manager/config.py`, add to the `DEFAULTS` dict:

```python
DEFAULTS = {
    "LOG_LEVEL": "INFO",
    "LOG_FILE": "logs/rclone_scripts.log",
    "DEFAULT_PORT": "8080",
    "INCLUDE_HIDDEN": "false",
    "USE_FZF": "true",
    "BIND_ADDRESS": "127.0.0.1",
    "ENABLE_XSRF_PROTECTION": "true",
    "ENABLE_CORS": "true",
}
```

- [ ] **Step 2: Update webui_launcher.py to respect config**

In `src/rclone_manager/webui_launcher.py`, replace the hardcoded flags with conditional ones:

```python
bind_addr = os.environ.get("BIND_ADDRESS", "127.0.0.1")
enable_xsrf = os.environ.get("ENABLE_XSRF_PROTECTION", "true").lower() == "true"
enable_cors = os.environ.get("ENABLE_CORS", "true").lower() == "true"

cmd = [
    sys.executable,
    "-m",
    "streamlit",
    "run",
    str(webui_path),
    f"--server.address={bind_addr}",
    "--server.port=8501",
]
if not enable_xsrf:
    cmd.append("--server.enableXsrfProtection=false")
if not enable_cors:
    cmd.append("--server.enableCORS=false")
if bind_addr != "0.0.0.0":
    cmd.append("--server.headless=true")
else:
    cmd.append("--server.headless=true")
```

(The `--server.headless=true` stays unconditional.)

- [ ] **Step 3: Update config.ini.example**

Add to `configs/config.ini.example` `[DEFAULT]` section:

```ini
; --- Web UI Security ---
; Enable Streamlit's built-in XSRF protection and CORS enforcement.
; Set to false only if connecting from non-browser clients on LAN.
ENABLE_XSRF_PROTECTION = true
ENABLE_CORS = true
```

- [ ] **Step 4: Run tests and lint**

```bash
uv run pytest tests/unit -v && uv run ruff check src/ tests/
```

Expected: all tests pass, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/rclone_manager/config.py src/rclone_manager/webui_launcher.py configs/config.ini.example
git commit -m "fix: make XSRF/CORS protection config-driven with secure defaults"
```

---

### Task 2: Pass password via env var instead of CLI args

**Files:**
- Modify: `src/rclone_manager/core.py:131-145` and `190-210`
- Test: `tests/unit/test_core.py` (no changes needed — existing tests don't assert `--user`/`--pass`)

**Rationale:** CLI args (`--user`/`--pass`) are visible to all users via `ps aux`. rclone natively reads `RCLONE_USER` and `RCLONE_PASS` env vars.

- [ ] **Step 1: Update _serve_remote_thread to use env vars**

In `src/rclone_manager/core.py`, find the `_serve_remote_thread` function. After the command list is built (around line 145), replace the `--user`/`--pass` flags with env vars.

Current code (approximately lines 134-146):
```python
command = [
    "rclone", "serve", backend,
    remote_path,
    "--addr", f":{port}",
    "--user", user,
    "--pass", passw,
    "--verbose",
]
```

Replace with:
```python
serve_env = os.environ.copy()
serve_env["RCLONE_USER"] = user
serve_env["RCLONE_PASS"] = passw

command = [
    "rclone", "serve", backend,
    remote_path,
    "--addr", f":{port}",
    "--verbose",
]
```

Then ensure the subprocess call uses this env. Find the line that runs the command (approximately line 152), it should be:
```python
subprocess.run(command + flags, capture_output=True)
```

Replace with:
```python
subprocess.run(command + flags, capture_output=True, env=serve_env)
```

- [ ] **Step 2: Do the same for the second serve path**

There's a second instance of `--user`/`--pass` in `_serve_remote_thread`'s Google Drive variant. Apply the same transformation — add env vars, remove `--user`/`--pass` from command.

The second variant is right after the first one (approximately lines 188-210). Apply the same `serve_env` + no `--user`/`--pass` pattern.

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_core.py -v
```

Expected: all tests pass. The `test_calls_rclone_serve` test checks for `"rclone"` and `"serve"` and `"http"` — those don't change.

- [ ] **Step 4: Commit**

```bash
git add src/rclone_manager/core.py
git commit -m "fix: pass rclone credentials via env vars instead of CLI args"
```

---

### Task 3: Set restrictive permissions on config files and registry

**Files:**
- Modify: `src/rclone_manager/config.py:49-57`
- Modify: `src/rclone_manager/mount.py:85-90`

**Rationale:** Config files contain credentials; registry JSON contains mount metadata (pid, rc port). Both should be owner-read-only.

- [ ] **Step 1: Add chmod to config.py setup_env**

In `src/rclone_manager/config.py`, after the config reading block (after line 57, inside `setup_env`), add:

```python
# Restrict permissions on config file to owner-only
if os.name != "nt" and os.path.exists(config_path):
    os.chmod(config_path, 0o600)
```

- [ ] **Step 2: Add chmod to mount.py _save_registry**

In `src/rclone_manager/mount.py`, in `_save_registry` around line 89, after `json.dump(registry, f, indent=2)`, add:

```python
# Restrict permissions to owner-only
if os.name != "nt":
    os.chmod(path, 0o600)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_config.py tests/unit/test_mount.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/rclone_manager/config.py src/rclone_manager/mount.py
git commit -m "fix: restrict config file and registry permissions to owner-only"
```

---

### Task 4: Remove `pass` fallback default for PASSWORD

**Files:**
- Modify: `src/rclone_manager/core.py:78-98`

**Rationale:** `os.environ.get("PASSWORD", "pass")` means anyone who serves without configuring a password gets `"pass"` as their auth credential. Force explicit configuration.

- [ ] **Step 1: Remove fallback default and add guard**

In `src/rclone_manager/core.py`, in `serve_remote()`, find lines 80-81:

```python
username = os.environ.get("USERNAME", "user")
password = os.environ.get("PASSWORD", "pass")
```

Replace with:

```python
username = os.environ.get("USERNAME", "user")
password = os.environ.get("PASSWORD")
if not password:
    console.print("[red]PASSWORD not set in environment or config. [/red]")
    console.print("[yellow]Set it in configs/config.ini under [DEFAULT]:[/yellow]")
    console.print("  PASSWORD = your_secret_password")
    return
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/unit/test_core.py -v
```

Expected: all tests pass. The existing `test_no_remotes_prints_message` test mocks `list_rclone_remotes` to return `[]`, so it doesn't reach the password check. No existing test calls `serve_remote` with a real remote, so the guard is untested but safe.

- [ ] **Step 3: Commit**

```bash
git add src/rclone_manager/core.py
git commit -m "fix: require PASSWORD to be explicitly configured, remove fallback default"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/unit -v && uv run ruff check src/ tests/
```

Expected: all tests pass, lint clean.

- [ ] **Step 2: Update CONTEXT.md**

Refresh the audit section to note the 4 new fixes. Mark resolved items and update "Recent Work".
