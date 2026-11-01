import os


class TestWebuiLauncher:
    def test_builds_default_streamlit_command(self, monkeypatch):
        from rclone_manager import webui_launcher

        captured = {}

        def fake_run(cmd, env=None):
            captured["cmd"] = cmd
            captured["env"] = env

        monkeypatch.setattr(webui_launcher, "get_ip_address", lambda: "10.0.0.2")
        monkeypatch.setattr(webui_launcher.subprocess, "run", fake_run)
        monkeypatch.delenv("BIND_ADDRESS", raising=False)
        monkeypatch.delenv("ENABLE_XSRF_PROTECTION", raising=False)
        monkeypatch.delenv("ENABLE_CORS", raising=False)
        monkeypatch.delenv("PYTHONPATH", raising=False)

        webui_launcher.main()

        assert captured["cmd"][1:3] == ["-m", "streamlit"]
        assert "run" in captured["cmd"]
        assert "--server.address=127.0.0.1" in captured["cmd"]
        assert "--server.port=8501" in captured["cmd"]
        assert "--server.headless=true" in captured["cmd"]
        assert not any("enableXsrfProtection" in part for part in captured["cmd"])
        assert not any("enableCORS" in part for part in captured["cmd"])

    def test_disables_xsrf_and_cors_when_requested(self, monkeypatch):
        from rclone_manager import webui_launcher

        captured = {}
        monkeypatch.setattr(webui_launcher, "get_ip_address", lambda: "10.0.0.2")
        monkeypatch.setattr(
            webui_launcher.subprocess,
            "run",
            lambda cmd, env=None: captured.update(cmd=cmd, env=env),
        )
        monkeypatch.setenv("ENABLE_XSRF_PROTECTION", "false")
        monkeypatch.setenv("ENABLE_CORS", "False")

        webui_launcher.main()

        assert "--server.enableXsrfProtection=false" in captured["cmd"]
        assert "--server.enableCORS=false" in captured["cmd"]

    def test_announces_lan_url_when_bound_to_all(self, monkeypatch, capsys):
        from rclone_manager import webui_launcher

        monkeypatch.setattr(webui_launcher, "get_ip_address", lambda: "192.168.1.50")
        monkeypatch.setattr(webui_launcher.subprocess, "run", lambda cmd, env=None: None)
        monkeypatch.setenv("BIND_ADDRESS", "0.0.0.0")

        webui_launcher.main()

        out = capsys.readouterr().out
        assert "http://localhost:8501" in out
        assert "http://192.168.1.50:8501" in out

    def test_prepends_existing_pythonpath(self, monkeypatch):
        from rclone_manager import webui_launcher

        captured = {}
        monkeypatch.setattr(webui_launcher, "get_ip_address", lambda: "10.0.0.2")
        monkeypatch.setattr(
            webui_launcher.subprocess,
            "run",
            lambda cmd, env=None: captured.update(env=env),
        )
        monkeypatch.setenv("PYTHONPATH", "/already/there")

        webui_launcher.main()

        parts = captured["env"]["PYTHONPATH"].split(os.pathsep)
        assert parts[-1] == "/already/there"
        assert len(parts) == 2

    def test_keyboard_interrupt_stops_cleanly(self, monkeypatch, capsys):
        from rclone_manager import webui_launcher

        def _interrupt(cmd, env=None):
            raise KeyboardInterrupt()

        monkeypatch.setattr(webui_launcher, "get_ip_address", lambda: "10.0.0.2")
        monkeypatch.setattr(webui_launcher.subprocess, "run", _interrupt)

        webui_launcher.main()

        assert "Web UI stopped." in capsys.readouterr().out
