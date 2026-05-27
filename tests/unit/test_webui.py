import json
import os
import subprocess
import tempfile



class FakeSessionState(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


class TestImport:
    def test_import_webui(self):
        from rclone_manager import webui

        assert hasattr(webui, "init_session_state")
        assert hasattr(webui, "list_rclone_remotes")
        assert hasattr(webui, "list_directory_contents")
        assert hasattr(webui, "list_remote_directory_contents")
        assert hasattr(webui, "download_files_as_zip")
        assert hasattr(webui, "main_app")


class TestListRcloneRemotes:
    def test_returns_remotes(self, monkeypatch):
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: b"remote1:\nremote2:\n",
        )
        from rclone_manager.webui import list_rclone_remotes

        assert list_rclone_remotes() == ["remote1", "remote2"]

    def test_filters_shared_remotes(self, monkeypatch):
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: b"remote1:\nremote1-shared:\n",
        )
        from rclone_manager.webui import list_rclone_remotes

        assert list_rclone_remotes() == ["remote1"]

    def test_file_not_found_returns_empty(self, monkeypatch):
        def _raise(*a, **kw):
            raise FileNotFoundError()

        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            _raise,
        )
        monkeypatch.setattr("rclone_manager.webui.st.error", lambda *a, **kw: None)
        from rclone_manager.webui import list_rclone_remotes

        assert list_rclone_remotes() == []


class TestListDirectoryContents:
    def test_returns_sorted_contents(self, monkeypatch):
        fake_state = FakeSessionState({"show_hidden": False})
        monkeypatch.setattr("rclone_manager.webui.st.session_state", fake_state)
        from rclone_manager.webui import list_directory_contents

        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "b_file.txt"), "w").close()
            open(os.path.join(tmpdir, "a_file.txt"), "w").close()
            os.makedirs(os.path.join(tmpdir, "a_dir"), exist_ok=True)

            contents = list_directory_contents(tmpdir)
            names = [c["name"] for c in contents]
            assert names[0] == "a_dir"
            assert names.index("a_file.txt") < names.index("b_file.txt")

    def test_permission_error_returns_empty(self, monkeypatch):
        def _raise(*a, **kw):
            raise PermissionError()

        monkeypatch.setattr("rclone_manager.webui.os.listdir", _raise)
        monkeypatch.setattr("rclone_manager.webui.st.error", lambda *a, **kw: None)
        monkeypatch.setattr(
            "rclone_manager.webui.st.session_state",
            FakeSessionState({"show_hidden": False}),
        )
        from rclone_manager.webui import list_directory_contents

        assert list_directory_contents("/some/path") == []


class TestListRemoteDirectoryContents:
    def test_returns_sorted_contents(self, monkeypatch):
        entries = [
            {"Name": "z_file.txt", "IsDir": False, "Size": 100, "ModTime": "2024-01-01"},
            {"Name": "a_dir", "IsDir": True, "Size": 0, "ModTime": "2024-01-01"},
        ]
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: json.dumps(entries).encode(),
        )
        monkeypatch.setattr(
            "rclone_manager.webui.st.session_state",
            FakeSessionState({"show_hidden": False}),
        )
        from rclone_manager.webui import list_remote_directory_contents

        contents = list_remote_directory_contents("remote:/path")
        names = [c["name"] for c in contents]
        assert names == ["a_dir", "z_file.txt"]

    def test_called_process_error_returns_empty(self, monkeypatch):
        def _raise(*a, **kw):
            raise subprocess.CalledProcessError(1, "rclone")

        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            _raise,
        )
        monkeypatch.setattr("rclone_manager.webui.st.error", lambda *a, **kw: None)
        from rclone_manager.webui import list_remote_directory_contents

        assert list_remote_directory_contents("remote:/path") == []

    def test_json_decode_error_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: b"invalid json",
        )
        monkeypatch.setattr("rclone_manager.webui.st.error", lambda *a, **kw: None)
        from rclone_manager.webui import list_remote_directory_contents

        assert list_remote_directory_contents("remote:/path") == []


class TestInitSessionState:
    def test_initializes_session_state(self, monkeypatch):
        fake_state = FakeSessionState()
        monkeypatch.setattr("rclone_manager.webui.st.session_state", fake_state)
        from rclone_manager.webui import init_session_state

        init_session_state()

        assert "current_path" in fake_state
        assert "selected_files" in fake_state
        assert "show_hidden" in fake_state
        assert "current_remote" in fake_state
        assert "remote_path" in fake_state
