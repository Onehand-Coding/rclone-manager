import subprocess

import pytest
from rclone_manager.ports import CommandResult
from rclone_manager.utils import (
    get_ip_address,
    run_rclone_with_retry,
)
from rclone_manager.remote_info import get_rclone_flags


class TestGetRcloneFlags:
    def test_empty_type_returns_empty_list(self):
        assert get_rclone_flags("") == []

    def test_no_env_var_returns_empty_list(self):
        assert get_rclone_flags("unknown") == []

    def test_single_flag_from_env(self, monkeypatch):
        monkeypatch.setenv("RCLONE_FLAGS_DRIVE", "--fast-list")
        assert get_rclone_flags("drive") == ["--fast-list"]

    def test_multiple_flags_split(self, monkeypatch):
        monkeypatch.setenv(
            "RCLONE_FLAGS_S3", "--fast-list --no-check-certificate --timeout=30s"
        )
        assert get_rclone_flags("s3") == [
            "--fast-list",
            "--no-check-certificate",
            "--timeout=30s",
        ]


class TestGetIpAddress:
    def test_returns_non_empty_string(self):
        ip = get_ip_address()
        assert isinstance(ip, str)
        assert len(ip) > 0


class TestRunRcloneWithRetry:
    def test_success_on_first_attempt(self, monkeypatch):
        fake_result = CommandResult(returncode=0, stdout="success", stderr="")
        monkeypatch.setattr("rclone_manager.utils._runner.run", lambda *a, **kw: fake_result)
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = run_rclone_with_retry(["rclone", "ls"])
        assert result.returncode == 0
        assert result.stdout == "success"

    def test_retries_on_transient_error_then_succeeds(self, monkeypatch):
        results = iter([
            CommandResult(returncode=1, stdout="", stderr="connection reset"),
            CommandResult(returncode=1, stdout="", stderr="connection reset"),
            CommandResult(returncode=0, stdout="ok", stderr=""),
        ])
        monkeypatch.setattr(
            "rclone_manager.utils._runner.run", lambda *a, **kw: next(results)
        )
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = run_rclone_with_retry(["rclone", "sync"], max_retries=3)
        assert result.returncode == 0
        assert result.stdout == "ok"

    def test_raises_after_all_retries_fail(self, monkeypatch):
        monkeypatch.setattr(
            "rclone_manager.utils._runner.run",
            lambda *a, **kw: (
                lambda: (_ for _ in ()).throw(
                    subprocess.TimeoutExpired(cmd="rclone", timeout=300)
                )
            )(),
        )
        monkeypatch.setattr("time.sleep", lambda s: None)

        with pytest.raises(subprocess.CalledProcessError):
            run_rclone_with_retry(["rclone", "sync"], max_retries=2)

    def test_returns_non_zero_for_non_retryable_error(self, monkeypatch):
        fake_result = CommandResult(returncode=1, stdout="", stderr="permission denied")
        monkeypatch.setattr("rclone_manager.utils._runner.run", lambda *a, **kw: fake_result)
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = run_rclone_with_retry(["rclone", "copy"], max_retries=3)
        assert result.returncode == 1
        assert "permission denied" in result.stderr
