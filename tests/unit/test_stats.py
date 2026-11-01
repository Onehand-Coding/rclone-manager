import json
import subprocess

from rclone_manager.ports import CommandResult

STATS_JSON = json.dumps(
    {
        "bytes": 2 * 1024 * 1024,
        "totalBytes": 4 * 1024 * 1024,
        "speed": 1024 * 1024,
        "transfers": 1,
        "totalTransfers": 2,
    }
)


class _StubRunner:
    """Runner whose popen returns a scripted process and run returns scripted results."""

    def __init__(self, responses, proc=None, run_exc=None):
        self.responses = list(responses)
        self.proc = proc
        self.run_exc = run_exc
        self.commands = []
        self.popen_kwargs = None

    def run(self, command, **kwargs):
        self.commands.append(command)
        if self.run_exc is not None:
            raise self.run_exc
        if not self.responses:
            raise AssertionError("no scripted response left")
        return self.responses.pop(0)

    def popen(self, command, **kwargs):
        self.commands.append(command)
        self.popen_kwargs = kwargs
        return self.proc


class _StubProc:
    """Process whose poll() walks a scripted list of returncodes."""

    def __init__(self, returncodes, stdin=None, stderr=None):
        self._returncodes = list(returncodes)
        self.returncode = None
        self.stdin = stdin
        self.stderr = stderr

    def poll(self):
        if self._returncodes:
            self.returncode = self._returncodes.pop(0)
        return self.returncode


class _Stdin:
    def __init__(self):
        self.data = ""
        self.closed = False

    def write(self, text):
        self.data += text

    def close(self):
        self.closed = True


class _RecordingOutput:
    def __init__(self):
        self.updates = []

    def print(self, *values, style=""):
        pass

    def status(self, message=""):
        outer = self

        class _Status:
            def update(self, text=""):
                outer.updates.append(text)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return _Status()


class TestGetRcStats:
    def test_returns_parsed_stats_on_success(self, monkeypatch):
        from rclone_manager import stats

        runner = _StubRunner([CommandResult(0, STATS_JSON)])
        monkeypatch.setattr(stats, "_runner", runner)

        assert stats._get_rc_stats(5580) == json.loads(STATS_JSON)
        assert runner.commands[0][:3] == ["rclone", "rc", "core/stats"]
        assert "--rc-addr=127.0.0.1:5580" in runner.commands[0]

    def test_returns_none_on_nonzero_exit(self, monkeypatch):
        from rclone_manager import stats

        monkeypatch.setattr(stats, "_runner", _StubRunner([CommandResult(1, STATS_JSON)]))

        assert stats._get_rc_stats(5580) is None

    def test_returns_none_on_timeout(self, monkeypatch):
        from rclone_manager import stats

        runner = _StubRunner(
            [], run_exc=subprocess.TimeoutExpired(cmd="rclone", timeout=3)
        )
        monkeypatch.setattr(stats, "_runner", runner)

        assert stats._get_rc_stats(5580) is None

    def test_returns_none_on_bad_json(self, monkeypatch):
        from rclone_manager import stats

        monkeypatch.setattr(stats, "_runner", _StubRunner([CommandResult(0, "not json")]))

        assert stats._get_rc_stats(5580) is None

    def test_returns_none_when_rclone_missing(self, monkeypatch):
        from rclone_manager import stats

        monkeypatch.setattr(stats, "_runner", _StubRunner([], run_exc=FileNotFoundError()))

        assert stats._get_rc_stats(5580) is None

    def test_returns_none_on_unexpected_error(self, monkeypatch):
        from rclone_manager import stats

        monkeypatch.setattr(stats, "_runner", _StubRunner([], run_exc=RuntimeError("boom")))

        assert stats._get_rc_stats(5580) is None


class TestRunRcloneWithStats:
    def test_appends_rc_flags_and_returns_success(self, monkeypatch):
        from rclone_manager import stats

        proc = _StubProc([0])
        runner = _StubRunner([], proc=proc)
        monkeypatch.setattr(stats, "_runner", runner)
        monkeypatch.setattr(stats, "console", _RecordingOutput())

        returncode, errors = stats._run_rclone_with_stats(
            "Syncing", ["rclone", "sync", "a", "b"], rc_port=5590
        )

        assert (returncode, errors) == (0, [])
        assert runner.commands[0] == [
            "rclone",
            "sync",
            "a",
            "b",
            "--rc",
            "--rc-addr=127.0.0.1:5590",
        ]

    def test_writes_stdin_data_when_given(self, monkeypatch):
        from rclone_manager import stats

        stdin = _Stdin()
        proc = _StubProc([0], stdin=stdin)
        monkeypatch.setattr(stats, "_runner", _StubRunner([], proc=proc))
        monkeypatch.setattr(stats, "console", _RecordingOutput())

        stats._run_rclone_with_stats("Syncing", ["rclone"], stdin_data="payload")

        assert stdin.data == "payload"
        assert stdin.closed is True

    def test_formats_transfer_and_size_while_running(self, monkeypatch):
        from rclone_manager import stats

        output = _RecordingOutput()
        proc = _StubProc([None, 0])
        runner = _StubRunner([CommandResult(0, STATS_JSON)], proc=proc)
        monkeypatch.setattr(stats, "_runner", runner)
        monkeypatch.setattr(stats, "console", output)
        monkeypatch.setattr(stats.time, "sleep", lambda seconds: None)

        returncode, _ = stats._run_rclone_with_stats("Syncing", ["rclone"])

        assert returncode == 0
        assert any("1/2 files" in u for u in output.updates)
        assert any("1.0 MB/s" in u for u in output.updates)
        assert any("2.0 MB / 4.0 MB" in u for u in output.updates)

    def test_formats_single_size_when_total_unknown(self, monkeypatch):
        from rclone_manager import stats

        output = _RecordingOutput()
        payload = json.dumps({"bytes": 1024 * 1024, "speed": 0})
        proc = _StubProc([None, 0])
        runner = _StubRunner([CommandResult(0, payload)], proc=proc)
        monkeypatch.setattr(stats, "_runner", runner)
        monkeypatch.setattr(stats, "console", output)
        monkeypatch.setattr(stats.time, "sleep", lambda seconds: None)

        stats._run_rclone_with_stats("Syncing", ["rclone"])

        assert any("0.0 MB/s  1.0 MB" in u for u in output.updates)
        assert not any("files" in u for u in output.updates)

    def test_shows_running_when_stats_empty(self, monkeypatch):
        from rclone_manager import stats

        output = _RecordingOutput()
        proc = _StubProc([None, 0])
        runner = _StubRunner([CommandResult(0, "{}")], proc=proc)
        monkeypatch.setattr(stats, "_runner", runner)
        monkeypatch.setattr(stats, "console", output)
        monkeypatch.setattr(stats.time, "sleep", lambda seconds: None)

        stats._run_rclone_with_stats("Syncing", ["rclone"])

        assert any("running..." in u for u in output.updates)

    def test_shows_running_when_stats_shape_is_wrong(self, monkeypatch):
        from rclone_manager import stats

        output = _RecordingOutput()
        proc = _StubProc([None, 0])
        runner = _StubRunner([CommandResult(0, '"unexpected"')], proc=proc)
        monkeypatch.setattr(stats, "_runner", runner)
        monkeypatch.setattr(stats, "console", output)
        monkeypatch.setattr(stats.time, "sleep", lambda seconds: None)

        stats._run_rclone_with_stats("Syncing", ["rclone"])

        assert any("running..." in u for u in output.updates)

    def test_returns_error_lines_on_failure(self, monkeypatch):
        from rclone_manager import stats

        import io

        proc = _StubProc([1], stderr=io.StringIO("ok line\n2026 ERROR disk full\n"))
        monkeypatch.setattr(stats, "_runner", _StubRunner([], proc=proc))
        monkeypatch.setattr(stats, "console", _RecordingOutput())

        returncode, errors = stats._run_rclone_with_stats("Syncing", ["rclone"])

        assert returncode == 1
        assert errors == ["2026 ERROR disk full"]

    def test_falls_back_to_last_lines_when_no_error_marker(self, monkeypatch):
        from rclone_manager import stats

        import io

        stderr = "\n".join(f"line {i}" for i in range(8))
        proc = _StubProc([1], stderr=io.StringIO(stderr))
        monkeypatch.setattr(stats, "_runner", _StubRunner([], proc=proc))
        monkeypatch.setattr(stats, "console", _RecordingOutput())

        _, errors = stats._run_rclone_with_stats("Syncing", ["rclone"])

        assert errors == ["line 3", "line 4", "line 5", "line 6", "line 7"]

    def test_no_errors_when_stderr_empty(self, monkeypatch):
        from rclone_manager import stats

        proc = _StubProc([1])
        monkeypatch.setattr(stats, "_runner", _StubRunner([], proc=proc))
        monkeypatch.setattr(stats, "console", _RecordingOutput())

        returncode, errors = stats._run_rclone_with_stats("Syncing", ["rclone"])

        assert (returncode, errors) == (1, [])
