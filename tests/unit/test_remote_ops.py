import json
import subprocess

from rclone_manager.ports import CommandResult


# ───────────────────────────── ls_remote ─────────────────────────────


class TestLsRemote:
    """ls_remote() — browse remote filesystem interactively."""

    LSJSON_DATA = [
        {"Name": "Docs", "IsDir": True, "Size": 0, "ModTime": "2024-01-15T10:00:00Z"},
        {"Name": "readme.txt", "IsDir": False, "Size": 1024, "ModTime": "2024-01-15T10:00:00Z"},
    ]

    LSJSON_DATA_LARGE = [
        {"Name": "big.iso", "IsDir": False, "Size": 1_073_741_824, "ModTime": "2024-06-01T00:00:00Z"},
        {"Name": "med.mp4", "IsDir": False, "Size": 1_048_576, "ModTime": "2024-06-01T00:00:00Z"},
        {"Name": "small.log", "IsDir": False, "Size": 512, "ModTime": "2024-06-01T00:00:00Z"},
    ]

    LSJSON_SUBDIR = [
        {"Name": "sub.doc", "IsDir": False, "Size": 2048, "ModTime": "2024-02-01T00:00:00Z"},
    ]

    # ── Early exits ──

    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: [])

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_no_remote_selected_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: None
        )

        from rclone_manager.remote_ops import ls_remote

        ls_remote()

    # ── lsjson errors ──

    def test_auth_error_on_lsjson(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )

        def _raise(*a, **kw):
            raise subprocess.CalledProcessError(1, a[0], stderr=b"invalid_grant")

        monkeypatch.setattr("rclone_manager.remote_ops._runner.check_output", _raise)

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("Authentication error" in m for m in test_output.messages)
        assert any("rclone config reconnect" in m for m in test_output.messages)

    def test_auth_error_token_lower(self, monkeypatch, test_output, fake_runner):
        """Auth error via 'token' keyword in stderr."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )

        def _raise(*a, **kw):
            raise subprocess.CalledProcessError(1, a[0], stderr=b"access token expired")

        monkeypatch.setattr("rclone_manager.remote_ops._runner.check_output", _raise)

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("Authentication error" in m for m in test_output.messages)

    def test_other_lsjson_error(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )

        def _raise(*a, **kw):
            raise subprocess.CalledProcessError(1, a[0], stderr=b"some error")

        monkeypatch.setattr("rclone_manager.remote_ops._runner.check_output", _raise)

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("Error listing path" in m for m in test_output.messages)

    # ── MEGA fallback → lsf ──

    def test_mega_fallback_lsf_success(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["mega_remote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "mega_remote"
        )

        call_count = 0

        def _side_effect(cmd, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"mega SIGSEGV")
            elif call_count == 2:
                return "Documents/\nPictures/\n"
            else:
                return "file1.txt\nfile2.txt\n"

        monkeypatch.setattr("rclone_manager.remote_ops._runner.check_output", _side_effect)
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("MEGA backend error" in m for m in test_output.messages)

    def test_mega_fallback_lsf_auth_error(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["mega_remote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "mega_remote"
        )

        call_count = 0

        def _side_effect(cmd, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"mega null pointer")
            else:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"invalid_grant")

        monkeypatch.setattr("rclone_manager.remote_ops._runner.check_output", _side_effect)

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("MEGA backend error" in m for m in test_output.messages)
        assert any("Authentication error" in m for m in test_output.messages)

    def test_mega_fallback_lsf_other_error(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["mega_remote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "mega_remote"
        )

        call_count = 0

        def _side_effect(cmd, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"mega nil pointer")
            else:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"random fail")

        monkeypatch.setattr("rclone_manager.remote_ops._runner.check_output", _side_effect)

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("MEGA backend error" in m for m in test_output.messages)
        assert any("Error listing path" in m for m in test_output.messages)

    # ── fzf path ──

    def test_fzf_quit_no_selection(self, monkeypatch, test_output, fake_runner):
        """fzf returns empty → break."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: True)
        monkeypatch.setattr("rclone_manager.remote_ops._run_fzf", lambda *a, **kw: [])

        from rclone_manager.remote_ops import ls_remote

        ls_remote()

    def test_fzf_quit_via_q(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: True)
        monkeypatch.setattr(
            "rclone_manager.remote_ops._run_fzf", lambda *a, **kw: ["q (quit)"]
        )

        from rclone_manager.remote_ops import ls_remote

        ls_remote()

    def test_fzf_go_up_at_root_noop(self, monkeypatch, test_output, fake_runner):
        """Going .. at root level is a no-op (continue in loop)."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        # Need the continue to re-list the same path
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))

        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: True)
        choices = iter([".. (go up)", "q (quit)"])

        def _fzf(items, **kw):
            return [next(choices)]

        monkeypatch.setattr("rclone_manager.remote_ops._run_fzf", _fzf)

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        # Should list the same path twice (both lsjson calls at root)
        assert fake_runner.commands.count(["rclone", "lsjson", "myremote:"]) == 2

    def test_fzf_navigate_into_dir_then_quit(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        # Root listing (has Docs dir)
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        # Subdirectory listing (empty)
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_SUBDIR)))

        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: True)
        choices = iter(["📁 Docs/", "q (quit)"])

        def _fzf(items, **kw):
            return [next(choices)]

        monkeypatch.setattr("rclone_manager.remote_ops._run_fzf", _fzf)

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        # Should have listed root then subdir
        cmds = [c for c in fake_runner.commands if "lsjson" in c]
        assert len(cmds) == 2
        assert cmds[0] == ["rclone", "lsjson", "myremote:"]
        assert cmds[1] == ["rclone", "lsjson", "myremote:/Docs/"]

    def test_fzf_go_up_from_subdir(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        # Root listing → docs dir
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        # Subdir listing → empty
        fake_runner.add_response(CommandResult(0, stdout=json.dumps([])))
        # Root listing again after go up
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))

        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: True)
        choices = iter(["📁 Docs/", ".. (go up)", "q (quit)"])

        def _fzf(items, **kw):
            return [next(choices)]

        monkeypatch.setattr("rclone_manager.remote_ops._run_fzf", _fzf)

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        cmds = [c for c in fake_runner.commands if "lsjson" in c]
        assert len(cmds) == 3
        assert cmds[0] == ["rclone", "lsjson", "myremote:"]
        assert cmds[1] == ["rclone", "lsjson", "myremote:/Docs/"]
        assert cmds[2] == ["rclone", "lsjson", "myremote:/"]

    def test_fzf_gb_size_formatting(self, monkeypatch, test_output, fake_runner):
        """Fzf path with large files hitting GB, MB, B formatting branches."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        # Data with all size ranges to exercise every branch
        data = [
            {"Name": "giant.iso", "IsDir": False, "Size": 2_000_000_000, "ModTime": "2024-06-01T00:00:00Z"},
            {"Name": "medium.mp4", "IsDir": False, "Size": 2_000_000, "ModTime": "2024-06-01T00:00:00Z"},
            {"Name": "small.log", "IsDir": False, "Size": 500, "ModTime": "2024-06-01T00:00:00Z"},
        ]
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(data)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: True)
        monkeypatch.setattr(
            "rclone_manager.remote_ops._run_fzf", lambda *a, **kw: ["q (quit)"]
        )

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        # The size formatting branches should all fire; no crash is sufficient

    # ── non-fzf path ──

    def test_non_fzf_empty_directory(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps([])))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("-- Empty --" in m for m in test_output.messages)

    def test_non_fzf_quit(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()

    def test_non_fzf_go_up_at_root(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        test_output.add_input_response("..")
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        # lsjson should be called twice on root
        cmds = [c for c in fake_runner.commands if "lsjson" in c]
        assert all(cmd == ["rclone", "lsjson", "myremote:"] for cmd in cmds)

    def test_non_fzf_enter_dir_then_quit(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_SUBDIR)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        test_output.add_input_response("1")
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        cmds = [c for c in fake_runner.commands if "lsjson" in c]
        assert len(cmds) == 2
        assert cmds[0] == ["rclone", "lsjson", "myremote:"]
        assert cmds[1] == ["rclone", "lsjson", "myremote:/Docs/"]

    def test_non_fzf_file_choice_shows_error(self, monkeypatch, test_output, fake_runner):
        """Selecting a file (not a dir) shows 'That's a file' message."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        # 1 dir (idx 0) + 1 file (idx 1)
        data = [
            {"Name": "Docs", "IsDir": True, "Size": 0, "ModTime": ""},
            {"Name": "file.txt", "IsDir": False, "Size": 100, "ModTime": ""},
        ]
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(data)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        # Entering "2" selects file.txt (index 1, which is >= len(dirs)=1)
        # After the error, the loop does `continue` which re-lists, so queue another response
        test_output.add_input_response("2")
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(data)))
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("not a folder" in m for m in test_output.messages)

    def test_non_fzf_invalid_input(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        # After the ValueError, the loop does `continue` which re-lists
        test_output.add_input_response("abc")
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        assert any("Invalid choice" in m for m in test_output.messages)

    def test_non_fzf_large_file_size_formatting(self, monkeypatch, test_output, fake_runner):
        """Verify different size formatting strings are hit."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA_LARGE)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        # These just need to not crash — size formatting already exercised
        assert any("GB" in m or "MB" in m or "B" in m for m in test_output.messages)

    def test_non_fzf_go_up_from_subdir(self, monkeypatch, test_output, fake_runner):
        """Navigate into a subdirectory and back up."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_SUBDIR)))
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(self.LSJSON_DATA)))
        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        test_output.add_input_response("1")
        test_output.add_input_response("..")
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        cmds = [c for c in fake_runner.commands if "lsjson" in c]
        assert len(cmds) == 3
        assert cmds[0] == ["rclone", "lsjson", "myremote:"]
        assert cmds[1] == ["rclone", "lsjson", "myremote:/Docs/"]
        assert cmds[2] == ["rclone", "lsjson", "myremote:"]

    def test_non_fzf_go_up_from_deep_subdir(self, monkeypatch, test_output, fake_runner):
        """Go up from a/b/ so os.path.dirname produces myremote:/a (not ending with ':') → line 216."""
        nested_root = [
            {"Name": "a", "IsDir": True, "Size": 0, "ModTime": ""},
        ]
        nested_a = [
            {"Name": "b", "IsDir": True, "Size": 0, "ModTime": ""},
        ]
        nested_b = [
            {"Name": "file.txt", "IsDir": False, "Size": 100, "ModTime": ""},
        ]

        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        # Root listing → dir "a"
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(nested_root)))
        # "myremote:/a/" listing → dir "b"
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(nested_a)))
        # "myremote:/a/b/" listing → has file
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(nested_b)))
        # After ".." from b, re-list "myremote:/a/"
        fake_runner.add_response(CommandResult(0, stdout=json.dumps(nested_a)))

        monkeypatch.setattr("rclone_manager.remote_ops._fzf_available", lambda: False)
        test_output.add_input_response("1")   # enter "a"
        test_output.add_input_response("1")   # enter "b" inside a
        test_output.add_input_response("..")  # go up (hits line 216: os.path.dirname → myremote:/a → += "/")
        test_output.add_input_response("q")

        from rclone_manager.remote_ops import ls_remote

        ls_remote()
        cmds = [c for c in fake_runner.commands if "lsjson" in c]
        assert len(cmds) == 4
        assert cmds[0] == ["rclone", "lsjson", "myremote:"]
        assert cmds[1] == ["rclone", "lsjson", "myremote:/a/"]
        assert cmds[2] == ["rclone", "lsjson", "myremote:/a/b/"]
        assert cmds[3] == ["rclone", "lsjson", "myremote:/a/"]


# ───────────────────────────── dedupe_remote ─────────────────────────────


class TestDedupeRemote:
    """dedupe_remote() — deduplicate files on a remote."""

    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: [])

        from rclone_manager.remote_ops import dedupe_remote

        dedupe_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_no_remote_selected_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: None
        )

        from rclone_manager.remote_ops import dedupe_remote

        dedupe_remote()

    def test_no_remote_path_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )

        from rclone_manager.remote_ops import dedupe_remote

        dedupe_remote()

    def test_no_mode_selected_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: "myremote:/path",
        )
        call_count = 0

        def _choose(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "myremote"
            return None  # No mode

        monkeypatch.setattr("rclone_manager.remote_ops.choose_from_list", _choose)

        from rclone_manager.remote_ops import dedupe_remote

        dedupe_remote()

    def test_interactive_mode_no_confirm_needed(self, monkeypatch, test_output, fake_runner):
        """'interactive' mode skips the confirm prompt."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: "myremote:/path",
        )
        fake_runner.add_response(CommandResult(0))
        call_count = 0

        def _choose(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "myremote"
            return "interactive"

        monkeypatch.setattr("rclone_manager.remote_ops.choose_from_list", _choose)

        from rclone_manager.remote_ops import dedupe_remote

        dedupe_remote()
        assert len(fake_runner.commands) == 1
        assert "dedupe" in fake_runner.commands[0]
        assert "--dedupe-mode=interactive" in fake_runner.commands[0]

    def test_non_interactive_cancelled(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: "myremote:/path",
        )

        call_count = 0

        def _choose(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "myremote"
            return "newest"

        monkeypatch.setattr("rclone_manager.remote_ops.choose_from_list", _choose)
        monkeypatch.setattr(
            "rclone_manager.remote_ops.console.input", lambda prompt="", **kw: "n"
        )

        from rclone_manager.remote_ops import dedupe_remote

        dedupe_remote()
        assert any("Cancelled" in m for m in test_output.messages)

    def test_non_interactive_confirmed(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: "myremote:/path",
        )
        fake_runner.add_response(CommandResult(0))

        call_count = 0

        def _choose(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "myremote"
            return "newest"

        monkeypatch.setattr("rclone_manager.remote_ops.choose_from_list", _choose)
        monkeypatch.setattr(
            "rclone_manager.remote_ops.console.input", lambda prompt="", **kw: "y"
        )

        from rclone_manager.remote_ops import dedupe_remote

        dedupe_remote()
        assert len(fake_runner.commands) == 1
        assert "dedupe" in fake_runner.commands[0]
        assert "--dedupe-mode=newest" in fake_runner.commands[0]


# ───────────────────────────── space_remote ─────────────────────────────


class TestSpaceRemote:
    """space_remote() — show remote storage usage."""

    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: [])

        from rclone_manager.remote_ops import space_remote

        space_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_no_remote_selected_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: None
        )

        from rclone_manager.remote_ops import space_remote

        space_remote()

    def test_remote_about_success(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(
            CommandResult(0, stdout="Storage: 1 TiB\nUsed: 200 GiB\n")
        )

        from rclone_manager.remote_ops import space_remote

        space_remote()
        assert len(fake_runner.commands) == 1
        assert "about" in fake_runner.commands[0]
        assert "myremote:" in fake_runner.commands[0]

    def test_remote_about_failure(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(
            CommandResult(1, stdout="", stderr="quota not available\n")
        )

        from rclone_manager.remote_ops import space_remote

        space_remote()
        assert any("quota info not available" in m for m in test_output.messages)

    def test_exception_during_about(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )

        def _raise(*a, **kw):
            raise RuntimeError("connection refused")

        monkeypatch.setattr("rclone_manager.remote_ops._runner.run", _raise)

        from rclone_manager.remote_ops import space_remote

        space_remote()
        assert any("Error checking" in m for m in test_output.messages)

    def test_multi_select_remotes(self, monkeypatch, test_output, fake_runner):
        """choose_from_list returns a list (multi=True path)."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["a", "b"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list",
            lambda *a, **kw: ["a", "b"],
        )
        fake_runner.add_response(CommandResult(0, stdout="Storage: 1 TiB\n"))
        fake_runner.add_response(CommandResult(0, stdout="Storage: 2 TiB\n"))

        from rclone_manager.remote_ops import space_remote

        space_remote()
        assert len(fake_runner.commands) == 2
        assert all("about" in c for c in fake_runner.commands)

    def test_multi_select_single_value_is_listified(self, monkeypatch, test_output, fake_runner):
        """When multi=True returns a single string, it's wrapped in a list."""
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list",
            lambda *a, **kw: "myremote",
        )
        fake_runner.add_response(CommandResult(0, stdout="Storage: 1 TiB\n"))

        from rclone_manager.remote_ops import space_remote

        space_remote()
        assert len(fake_runner.commands) == 1


# ───────────────────────────── copy_between ─────────────────────────────


class TestCopyBetween:
    """copy_between() — copy files between two remotes."""

    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: [])

        from rclone_manager.remote_ops import copy_between

        copy_between()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_no_source_remote_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: None
        )

        from rclone_manager.remote_ops import copy_between

        copy_between()

    def test_no_source_path_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )

        from rclone_manager.remote_ops import copy_between

        copy_between()

    def test_no_dest_remote_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: "myremote:/src",
        )
        call_count = 0

        def _choose(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "myremote"
            return None  # No dest remote

        monkeypatch.setattr("rclone_manager.remote_ops.choose_from_list", _choose)

        from rclone_manager.remote_ops import copy_between

        copy_between()

    def test_no_dest_path_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])

        nav_count = 0

        def _nav(*a, **kw):
            nonlocal nav_count
            nav_count += 1
            if nav_count == 1:
                return "myremote:/src"
            return None  # No dest path

        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system", _nav
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )

        from rclone_manager.remote_ops import copy_between

        copy_between()

    def test_successful_copy(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["remote1", "remote2"])

        nav_calls = iter(["remote1:/src", "remote2:/dst"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: next(nav_calls),
        )

        stats_calls = []
        monkeypatch.setattr(
            "rclone_manager.remote_ops._run_rclone_with_stats",
            lambda label, cmd: stats_calls.append((label, cmd)) or (0, []),
        )

        choose_calls = iter(["remote1", "remote2"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list",
            lambda *a, **kw: next(choose_calls),
        )

        from rclone_manager.remote_ops import copy_between

        copy_between()
        assert len(stats_calls) == 1
        label, cmd = stats_calls[0]
        assert label == "Copying"
        assert cmd == ["rclone", "copy", "remote1:/src", "remote2:/dst"]

    def test_failed_copy(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["remote1", "remote2"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: "remote1:/src" if "src" not in str(kw) else "remote2:/dst",
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops._run_rclone_with_stats",
            lambda label, cmd: (1, ["ERROR : file copy failed"]),
        )

        call_count = 0

        def _choose(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "remote1"
            return "remote2"

        monkeypatch.setattr("rclone_manager.remote_ops.choose_from_list", _choose)

        from rclone_manager.remote_ops import copy_between

        copy_between()
        assert any("Copy failed" in m for m in test_output.messages)
        assert any("file copy failed" in m for m in test_output.messages)


# ───────────────────────────── bisync_remotes ─────────────────────────────


class TestBisyncRemotes:
    """bisync_remotes() — bidirectional sync between two remotes."""

    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: [])

        from rclone_manager.remote_ops import bisync_remotes

        bisync_remotes()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_no_remote1_selected(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: None
        )

        from rclone_manager.remote_ops import bisync_remotes

        bisync_remotes()

    def test_no_path1_selected(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "myremote"
        )

        from rclone_manager.remote_ops import bisync_remotes

        bisync_remotes()

    def test_no_remote2_selected(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["a", "b"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: "a:/path1",
        )

        call_count = 0

        def _choose(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "a"
            return None

        monkeypatch.setattr("rclone_manager.remote_ops.choose_from_list", _choose)

        from rclone_manager.remote_ops import bisync_remotes

        bisync_remotes()

    def test_no_path2_selected(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["a", "b"])

        nav_count = 0

        def _nav(*a, **kw):
            nonlocal nav_count
            nav_count += 1
            if nav_count == 1:
                return "a:/path1"
            return None

        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system", _nav
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "b"
        )

        from rclone_manager.remote_ops import bisync_remotes

        bisync_remotes()

    def test_with_resync_success(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["a", "b"])

        nav_calls = iter(["a:/p1", "b:/p2"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: next(nav_calls),
        )

        stats_calls = []
        monkeypatch.setattr(
            "rclone_manager.remote_ops._run_rclone_with_stats",
            lambda label, cmd: stats_calls.append((label, cmd)) or (0, []),
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.console.input",
            lambda prompt="", **kw: "y",
        )

        choose_calls = iter(["a", "b"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list",
            lambda *a, **kw: next(choose_calls),
        )

        from rclone_manager.remote_ops import bisync_remotes

        bisync_remotes()
        assert len(stats_calls) == 1
        label, cmd = stats_calls[0]
        assert label == "Bisync"
        assert cmd == ["rclone", "bisync", "a:/p1", "b:/p2", "--resync"]

    def test_without_resync_success(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["a", "b"])

        nav_calls = iter(["a:/p1", "b:/p2"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: next(nav_calls),
        )

        stats_calls = []
        monkeypatch.setattr(
            "rclone_manager.remote_ops._run_rclone_with_stats",
            lambda label, cmd: stats_calls.append((label, cmd)) or (0, []),
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.console.input",
            lambda prompt="", **kw: "n",
        )

        choose_calls = iter(["a", "b"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list",
            lambda *a, **kw: next(choose_calls),
        )

        from rclone_manager.remote_ops import bisync_remotes

        bisync_remotes()
        assert len(stats_calls) == 1
        label, cmd = stats_calls[0]
        assert label == "Bisync"
        assert cmd == ["rclone", "bisync", "a:/p1", "b:/p2"]
        assert "--resync" not in cmd

    def test_bisync_failure(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.remote_ops.console", test_output)
        monkeypatch.setattr("rclone_manager.remote_ops._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.remote_ops.list_rclone_remotes", lambda: ["a", "b"])
        monkeypatch.setattr(
            "rclone_manager.remote_ops.navigate_remote_file_system",
            lambda *a, **kw: "a:/p1" if "first" in str(kw.get("purpose", "")) else "b:/p2",
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops._run_rclone_with_stats",
            lambda label, cmd: (1, ["ERROR : sync conflict detected"]),
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.console.input",
            lambda prompt="", **kw: "n",
        )
        monkeypatch.setattr(
            "rclone_manager.remote_ops.choose_from_list", lambda *a, **kw: "a" if "first" in str(a) else "b"
        )

        from rclone_manager.remote_ops import bisync_remotes

        bisync_remotes()
        assert any("Bisync failed" in m for m in test_output.messages)
        assert any("sync conflict detected" in m for m in test_output.messages)
