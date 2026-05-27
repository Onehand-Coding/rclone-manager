
from rclone_manager.ports import CommandResult

# All patching uses string paths to target the correct module-level name bindings


class TestCheckRemote:
    def test_no_local_path_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.core.navigate_local_file_system",
            lambda purpose=None, **kw: None,
        )

        from rclone_manager.core import check_remote

        check_remote()

    def test_no_remotes_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.core.navigate_local_file_system",
            lambda purpose=None, **kw: "/local/path",
        )
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: [])

        from rclone_manager.core import check_remote

        check_remote()

    def test_calls_rclone_check(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.core.navigate_local_file_system",
            lambda purpose=None, **kw: "/local/path",
        )
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr("rclone_manager.core._runner", fake_runner)
        monkeypatch.setattr(
            "rclone_manager.core.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: "myremote:/backup",
        )
        monkeypatch.setattr(
            "rclone_manager.core.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0))

        from rclone_manager.core import check_remote

        check_remote()
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "rclone" in last_cmd
        assert "check" in last_cmd
        assert "/local/path" in last_cmd
        assert "myremote:/backup" in last_cmd


class TestGenerateDefaultConfig:
    def test_creates_config_when_missing(self, monkeypatch, tmp_path, test_output):
        monkeypatch.setattr("rclone_manager.core.get_project_root", lambda: str(tmp_path))
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        (tmp_path / "configs").mkdir()

        from rclone_manager.core import generate_default_config

        generate_default_config()

        config_file = tmp_path / "configs" / "config.ini"
        assert config_file.exists()
        content = config_file.read_text()
        assert "log_level" in content.lower()
        assert "rclone_flags" in content

    def test_skips_when_config_exists(self, monkeypatch, tmp_path, test_output):
        configs = tmp_path / "configs"
        configs.mkdir()
        existing = configs / "config.ini"
        existing.write_text("[DEFAULT]\nkey = original\n")

        monkeypatch.setattr("rclone_manager.core.get_project_root", lambda: str(tmp_path))
        monkeypatch.setattr("rclone_manager.core.console", test_output)

        from rclone_manager.core import generate_default_config

        generate_default_config()
        assert existing.read_text() == "[DEFAULT]\nkey = original\n"
        assert any("already exists" in m for m in test_output.messages)


class TestServeLocal:
    def test_no_path_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.core.navigate_local_file_system",
            lambda purpose=None, **kw: None,
        )

        from rclone_manager.core import serve_local

        serve_local()

    def test_calls_rclone_serve(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.core.navigate_local_file_system",
            lambda purpose=None, **kw: "/serve/path",
        )
        monkeypatch.setattr("rclone_manager.core._runner", fake_runner)
        monkeypatch.setattr(
            "rclone_manager.core.choose_from_list", lambda *a, **kw: "http"
        )
        fake_runner.add_response(CommandResult(0))

        from rclone_manager.core import serve_local

        serve_local()
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "rclone" in last_cmd
        assert "serve" in last_cmd
        assert "http" in last_cmd
        assert "/serve/path" in last_cmd


class TestDedupeRemote:
    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: [])

        from rclone_manager.core import dedupe_remote

        dedupe_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_calls_rclone_dedupe(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr("rclone_manager.core._runner", fake_runner)
        monkeypatch.setattr(
            "rclone_manager.core.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: "myremote:/dedupe",
        )
        fake_runner.add_response(CommandResult(0))

        choose_iter = iter(["myremote", "newest"])
        monkeypatch.setattr(
            "rclone_manager.core.choose_from_list", lambda *a, **kw: next(choose_iter)
        )
        # Replace console.input so it accepts kwargs and returns "y" for the confirm prompt
        monkeypatch.setattr(
            "rclone_manager.core.console.input",
            lambda prompt="", **kw: "y",
        )

        from rclone_manager.core import dedupe_remote

        dedupe_remote()
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "dedupe" in last_cmd


class TestSpaceRemote:
    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: [])

        from rclone_manager.core import space_remote

        space_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_calls_rclone_about(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr("rclone_manager.core._runner", fake_runner)
        monkeypatch.setattr(
            "rclone_manager.core.choose_from_list", lambda *a, **kw: "myremote"
        )
        fake_runner.add_response(CommandResult(0, stdout="Storage: 1TB\nUsed: 200GB\n"))

        from rclone_manager.core import space_remote

        space_remote()
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "about" in last_cmd


class TestLsRemote:
    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: [])

        from rclone_manager.core import ls_remote

        ls_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)


class TestServeRemote:
    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: [])

        from rclone_manager.core import serve_remote

        serve_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)


class TestCopyBetween:
    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: [])

        from rclone_manager.core import copy_between

        copy_between()
        assert any("No rclone remotes" in m for m in test_output.messages)


class TestBisyncRemotes:
    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.core.console", test_output)
        monkeypatch.setattr("rclone_manager.core.list_rclone_remotes", lambda: [])

        from rclone_manager.core import bisync_remotes

        bisync_remotes()
        assert any("No rclone remotes" in m for m in test_output.messages)
