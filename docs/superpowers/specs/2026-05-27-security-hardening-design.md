# Security Hardening — Minimal Viable Security

> Date: 2026-05-27
> Status: Approved

## Overview

Fix 5 remaining security issues from the audit, keeping changes surgical and low-risk.

## Changes

### 1. Enable XSRF/CORS protection by default

**Motivation:** `webui_launcher.py` hardcodes `--server.enableCORS=false` and `--server.enableXsrfProtection=false`, disabling Streamlit's built-in CSRF and CORS protection.

**Fix:**
- Add `ENABLE_XSRF_PROTECTION = true` and `ENABLE_CORS = true` to `config.py` DEFAULTS
- In `webui_launcher.py`, read env vars and only add `--server.enableXsrfProtection=false` / `--server.enableCORS=false` when the corresponding config is explicitly `false`
- Document both options in `config.ini.example`

### 2. Pass password via env var instead of CLI args

**Motivation:** `_serve_remote_thread` passes `--user` and `--pass` as rclone CLI flags (lines 140-142, 200-203 of core.py), making passwords visible to all users via `ps aux`.

**Fix:**
- Remove `--user` and `--pass` from the rclone command list
- Set `RCLONE_USER` and `RCLONE_PASS` in the subprocess environment dict instead
- rclone natively reads these env vars for authentication

### 3. Restrictive permissions on config files and registry

**Motivation:** Config files containing credentials and mount registry (PID/port info) are created with default umask permissions.

**Fix:**
- In `config.py` `setup_env()`: after reading config, call `os.chmod(path, 0o600)` on the config file
- In `mount.py` `_save_registry()`: after writing, call `os.chmod(path, 0o600)` on the registry file
- Guard with `if os.name != "nt":` to skip on Windows

### 4. Remove `pass` fallback defaults for `PASSWORD`

**Motivation:** `os.environ.get("PASSWORD", "pass")` at core.py lines 81 and 188 defaults to `"pass"` when no password is configured, serving with a trivially guessable credential.

**Fix:**
- Remove the `"pass"` fallback from both locations
- If `PASSWORD` is unset, print `[red]PASSWORD not set in config.[/red]` and return early instead of serving
- The serve thread loops in `serve_remote()` will skip jobs with no password

## Files Modified

| File | Change |
|------|--------|
| `src/rclone_manager/config.py` | Add `ENABLE_XSRF_PROTECTION`, `ENABLE_CORS` to DEFAULTS; add `os.chmod(0o600)` after config load |
| `src/rclone_manager/webui_launcher.py` | Read `ENABLE_XSRF_PROTECTION`/`ENABLE_CORS` env vars, conditionally pass Streamlit flags |
| `src/rclone_manager/core.py` | Remove `--user`/`--pass` from commands, use `RCLONE_USER`/`RCLONE_PASS` env vars instead; require PASSWORD to be set |
| `src/rclone_manager/mount.py` | Add `os.chmod(0o600)` in `_save_registry()` |
| `configs/config.ini.example` | Document `enable_xsrf_protection`, `enable_cors` options |

## Testing

- Existing unit tests for `core.py` serve functions should still pass (command structure changes, but test doubles capture both CLI args and env)
- Update `test_core.py` if any test asserts the old `--user`/`--pass` CLI pattern
- Update `test_mount.py` if registry path assertions are affected
- Confirm `ruff check` passes

## Risk Assessment

- WebUI XSRF/CORS change: users accessing from LAN with `bind_address = 0.0.0.0` may need to add `enable_cors = false` to config — non-breaking due to config-driven approach
- Password env var change: no functional difference, rclone reads both
- Permissions change: `os.chmod` silently ignored on Windows (guard already in place); on Linux/macOS no-op if owner already has access
- Password fallback removal: users who depended on the `"pass"` default will get an error on serve — this is the intended behavior
