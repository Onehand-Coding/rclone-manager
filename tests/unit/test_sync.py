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
