class TestSyncRemotes:
    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync.console", test_output)
        monkeypatch.setattr("rclone_manager.sync.list_rclone_remotes", lambda: [])

        from rclone_manager.sync import sync_remotes

        sync_remotes()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_no_source_selection_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync.list_rclone_remotes", lambda: ["remote1", "remote2"]
        )
        monkeypatch.setattr(
            "rclone_manager.sync.choose_from_list", lambda *a, **kw: None
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes()

    def test_dry_run_mode(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync.list_rclone_remotes", lambda: ["remote1", "remote2"]
        )
        monkeypatch.setattr(
            "rclone_manager.sync.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: f"{remote}:/path",
        )

        captured_commands = []

        def fake_stats(label, cmd, **kw):
            captured_commands.append(cmd)
            return (0, [])

        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", fake_stats
        )

        choose_results = iter(["remote1", "remote2"])
        monkeypatch.setattr(
            "rclone_manager.sync.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(dry_run=True)
        assert len(captured_commands) >= 1
        last_cmd = captured_commands[-1]
        assert "rclone" in last_cmd
        assert "sync" in last_cmd
        assert "--dry-run" in last_cmd

    def test_sync_failure_reported(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync.list_rclone_remotes", lambda: ["remote1", "remote2"]
        )
        monkeypatch.setattr(
            "rclone_manager.sync.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: f"{remote}:/path",
        )
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats",
            lambda label, cmd: (1, ["Error: sync failed"]),
        )

        choose_results = iter(["remote1", "remote2"])
        monkeypatch.setattr(
            "rclone_manager.sync.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(force=True)
        assert any("Sync failed" in m for m in test_output.messages)


class _ScriptedRunner:
    def __init__(self, results):
        self.results = list(results)
        self.commands = []

    def run(self, command, **kwargs):
        self.commands.append(command)
        return self.results.pop(0)


def _wire_selection(monkeypatch, test_output, paths=("remote1:/src", "remote2:/dst")):
    monkeypatch.setattr("rclone_manager.sync.console", test_output)
    monkeypatch.setattr(
        "rclone_manager.sync.list_rclone_remotes", lambda: ["remote1", "remote2"]
    )
    choices = iter(["remote1", "remote2"])
    monkeypatch.setattr(
        "rclone_manager.sync.choose_from_list", lambda *a, **kw: next(choices)
    )
    path_iter = iter(paths)
    monkeypatch.setattr(
        "rclone_manager.sync.navigate_remote_file_system",
        lambda remote, purpose=None, **kw: next(path_iter),
    )


class TestSyncPreview:
    def test_reports_source_destination_and_differing_files(
        self, monkeypatch, test_output
    ):
        from rclone_manager.ports import CommandResult

        _wire_selection(monkeypatch, test_output)
        runner = _ScriptedRunner(
            [
                CommandResult(1, "", "ERROR : a.txt: file not in one directory\n"),
                CommandResult(1, "", "ERROR : b.txt: file not in Local\n"),
                CommandResult(1, "", "ERROR : c.txt: Sizes differ\n"),
            ]
        )
        monkeypatch.setattr("rclone_manager.sync._runner", runner)
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", lambda label, cmd: (0, [])
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(preview=True, force=True)

        assert any("1 files only in SOURCE" in m for m in test_output.messages)
        assert any("1 files only in DESTINATION" in m for m in test_output.messages)
        assert any("1 files differ" in m for m in test_output.messages)
        assert any("+ a.txt" in m for m in test_output.messages)
        assert any("- b.txt" in m for m in test_output.messages)
        assert any("~ c.txt" in m for m in test_output.messages)

    def test_truncates_long_preview_lists(self, monkeypatch, test_output):
        from rclone_manager.ports import CommandResult

        _wire_selection(monkeypatch, test_output)
        lines = "".join(
            f"ERROR : file{i}.txt: file not in one directory\n" for i in range(11)
        )
        runner = _ScriptedRunner(
            [
                CommandResult(1, "", lines),
                CommandResult(0, "", ""),
                CommandResult(0, "", ""),
            ]
        )
        monkeypatch.setattr("rclone_manager.sync._runner", runner)
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", lambda label, cmd: (0, [])
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(preview=True, force=True)

        assert any("11 files only in SOURCE" in m for m in test_output.messages)
        assert any("and 1 more" in m for m in test_output.messages)

    def test_reports_identical_files(self, monkeypatch, test_output):
        from rclone_manager.ports import CommandResult

        _wire_selection(monkeypatch, test_output)
        runner = _ScriptedRunner(
            [CommandResult(0, "", ""), CommandResult(0, "", ""), CommandResult(0, "", "")]
        )
        monkeypatch.setattr("rclone_manager.sync._runner", runner)
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", lambda label, cmd: (0, [])
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(preview=True, force=True)

        assert any("No differences found" in m for m in test_output.messages)

    def test_ignores_unrecognised_preview_lines(self, monkeypatch, test_output):
        from rclone_manager.ports import CommandResult

        _wire_selection(monkeypatch, test_output)
        runner = _ScriptedRunner(
            [
                CommandResult(0, "", "noise without a colon\nstill noise\n"),
                CommandResult(0, "", "noise\n"),
                CommandResult(0, "", "noise\n"),
            ]
        )
        monkeypatch.setattr("rclone_manager.sync._runner", runner)
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", lambda label, cmd: (0, [])
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(preview=True, force=True)

        assert any("No differences found" in m for m in test_output.messages)

    def test_preview_failure_is_reported(self, monkeypatch, test_output):
        _wire_selection(monkeypatch, test_output)

        class _FailingRunner:
            def run(self, command, **kwargs):
                raise RuntimeError("rclone exploded")

        monkeypatch.setattr("rclone_manager.sync._runner", _FailingRunner())
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", lambda label, cmd: (0, [])
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(preview=True, force=True)

        assert any("Preview failed" in m for m in test_output.messages)


class TestSyncConfirmation:
    def test_cancel_skips_sync(self, monkeypatch, test_output):
        _wire_selection(monkeypatch, test_output)
        calls = []
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats",
            lambda label, cmd: calls.append(cmd) or (0, []),
        )
        monkeypatch.setattr(
            "rich.prompt.Confirm.ask", staticmethod(lambda *a, **kw: False)
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes()

        assert calls == []
        assert any("Sync cancelled" in m for m in test_output.messages)

    def test_confirm_runs_sync(self, monkeypatch, test_output):
        _wire_selection(monkeypatch, test_output)
        calls = []
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats",
            lambda label, cmd: calls.append(cmd) or (0, []),
        )
        monkeypatch.setattr(
            "rich.prompt.Confirm.ask", staticmethod(lambda *a, **kw: True)
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes()

        assert len(calls) == 1
        assert any("Sync complete" in m for m in test_output.messages)

    def test_dry_run_success_message(self, monkeypatch, test_output):
        _wire_selection(monkeypatch, test_output)
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", lambda label, cmd: (0, [])
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(dry_run=True)

        assert any("Dry run complete" in m for m in test_output.messages)


class TestSyncEarlyReturns:
    def test_no_destination_selection_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync.list_rclone_remotes", lambda: ["remote1", "remote2"]
        )
        monkeypatch.setattr(
            "rclone_manager.sync.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: f"{remote}:/path",
        )
        choices = iter(["remote1", None])
        monkeypatch.setattr(
            "rclone_manager.sync.choose_from_list", lambda *a, **kw: next(choices)
        )
        calls = []
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats",
            lambda label, cmd: calls.append(cmd) or (0, []),
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(force=True)

        assert calls == []

    def test_empty_destination_path_returns_early(self, monkeypatch, test_output):
        _wire_selection(monkeypatch, test_output, paths=("remote1:/src", None))
        calls = []
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats",
            lambda label, cmd: calls.append(cmd) or (0, []),
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(force=True)

        assert calls == []


class TestSyncPreviewTruncation:
    def test_truncates_destination_list(self, monkeypatch, test_output):
        from rclone_manager.ports import CommandResult

        _wire_selection(monkeypatch, test_output)
        lines = "".join(
            f"ERROR : b{i}.txt: file not in Local\n" for i in range(11)
        )
        runner = _ScriptedRunner(
            [
                CommandResult(0, "", ""),
                CommandResult(1, "", lines),
                CommandResult(0, "", ""),
            ]
        )
        monkeypatch.setattr("rclone_manager.sync._runner", runner)
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", lambda label, cmd: (0, [])
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(preview=True, force=True)

        assert any("11 files only in DESTINATION" in m for m in test_output.messages)
        assert any("and 1 more" in m for m in test_output.messages)

    def test_truncates_differing_list(self, monkeypatch, test_output):
        from rclone_manager.ports import CommandResult

        _wire_selection(monkeypatch, test_output)
        lines = "".join(f"ERROR : c{i}.txt: Sizes differ\n" for i in range(11))
        runner = _ScriptedRunner(
            [
                CommandResult(0, "", ""),
                CommandResult(0, "", ""),
                CommandResult(1, "", lines),
            ]
        )
        monkeypatch.setattr("rclone_manager.sync._runner", runner)
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats", lambda label, cmd: (0, [])
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(preview=True, force=True)

        assert any("11 files differ" in m for m in test_output.messages)
        assert any("and 1 more" in m for m in test_output.messages)


class TestSyncEmptyPaths:
    def test_empty_source_path_returns_early(self, monkeypatch, test_output):
        _wire_selection(monkeypatch, test_output, paths=(None, "remote2:/dst"))
        calls = []
        monkeypatch.setattr(
            "rclone_manager.sync._run_rclone_with_stats",
            lambda label, cmd: calls.append(cmd) or (0, []),
        )

        from rclone_manager.sync import sync_remotes

        sync_remotes(force=True)

        assert calls == []
