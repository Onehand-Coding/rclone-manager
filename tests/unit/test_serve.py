from rclone_manager.ports import CommandResult, TestOutput as _TestOutput


class _NoLiveStatus(_TestOutput):
    def status(self, message: str = ""):
        raise RuntimeError("serve threads must not use console.status()")


class TestServeRemote:
    def test_serve_thread_prints_status_without_shared_live(self, monkeypatch, fake_runner):
        out = _NoLiveStatus()
        monkeypatch.setattr("rclone_manager.serve.console", out)
        monkeypatch.setattr("rclone_manager.serve._runner", fake_runner)
        monkeypatch.setattr("rclone_manager.serve.get_remote_type", lambda r: "mega")
        fake_runner.add_response(CommandResult(0))

        from rclone_manager.serve import _serve_remote_thread

        _serve_remote_thread("myremote", "http", 8080, "user", "pass", False)
        assert any("Serving myremote" in m for m in out.messages)

    def test_no_remotes_prints_message(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.serve.console", test_output)
        monkeypatch.setattr("rclone_manager.serve.list_rclone_remotes", lambda: [])

        from rclone_manager.serve import serve_remote

        serve_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)

    def test_no_selection_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.serve.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.serve.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.serve.choose_from_list", lambda *a, **kw: None
        )

        from rclone_manager.serve import serve_remote

        serve_remote()

    def test_no_password_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.serve.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.serve.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.serve.get_remote_type", lambda r: "mega"
        )
        monkeypatch.setattr(
            "rclone_manager.serve.choose_from_list",
            lambda *a, **kw: ["myremote"] if kw.get("multi") else "http",
        )

        from rclone_manager.serve import serve_remote

        serve_remote()
        assert any("PASSWORD not set" in m for m in test_output.messages)

    def test_starts_serve_thread(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.serve.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.serve.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.serve.get_remote_type", lambda r: "mega"
        )
        monkeypatch.setattr(
            "rclone_manager.serve.choose_from_list",
            lambda *a, **kw: ["myremote"] if kw.get("multi") else "http",
        )
        monkeypatch.setattr("rclone_manager.serve._runner", fake_runner)
        monkeypatch.setenv("PASSWORD", "secret123")
        fake_runner.add_response(CommandResult(0))

        from rclone_manager.serve import serve_remote

        serve_remote()
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "rclone" in last_cmd
        assert "serve" in last_cmd
        assert "http" in last_cmd


class TestServeLocal:
    def test_no_path_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.serve.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.serve.navigate_local_file_system",
            lambda purpose=None, **kw: None,
        )

        from rclone_manager.serve import serve_local

        serve_local()

    def test_calls_rclone_serve(self, monkeypatch, test_output, fake_runner):
        monkeypatch.setattr("rclone_manager.serve.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.serve.navigate_local_file_system",
            lambda purpose=None, **kw: "/serve/path",
        )
        monkeypatch.setattr("rclone_manager.serve._runner", fake_runner)
        monkeypatch.setattr(
            "rclone_manager.serve.choose_from_list", lambda *a, **kw: "http"
        )
        monkeypatch.setenv("USERNAME", "user")
        monkeypatch.setenv("PASSWORD", "pass")
        fake_runner.add_response(CommandResult(0))

        from rclone_manager.serve import serve_local

        serve_local()
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "rclone" in last_cmd
        assert "serve" in last_cmd
        assert "http" in last_cmd
        assert "/serve/path" in last_cmd

        assert "--user" not in last_cmd
        assert "--pass" not in last_cmd

        assert len(fake_runner.kwargs) >= 1
        last_kwargs = fake_runner.kwargs[-1]
        assert "env" in last_kwargs
        assert last_kwargs["env"].get("RCLONE_USER") == "user"
        assert last_kwargs["env"].get("RCLONE_PASS") == "pass"
