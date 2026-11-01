import json
import os
import subprocess
import tempfile
from zipfile import ZipFile


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
        assert hasattr(webui, "download_remote_files_as_zip")
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


class TestRemoteItemName:
    def test_returns_item_name(self):
        from rclone_manager.webui import _remote_item_name

        assert _remote_item_name("remote:file.txt") == "file.txt"
        assert _remote_item_name("remote:/a/b") == "b"
        assert _remote_item_name("remote:/a/b/") == "b"


class TestIsRemoteDir:
    def test_file_returns_false(self, monkeypatch):
        entries = json.dumps([{"Path": "file.txt", "Name": "file.txt", "IsDir": False}])
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: entries.encode(),
        )
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:file.txt") is False

    def test_dir_returns_true(self, monkeypatch):
        entries = json.dumps([{"Path": "child.txt", "Name": "child.txt", "IsDir": False}])
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: entries.encode(),
        )
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:/dir") is True

    def test_empty_dir_returns_true(self, monkeypatch):
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: b"[]",
        )
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:/empty") is True

    def test_called_process_error_returns_false(self, monkeypatch):
        def _raise(*a, **kw):
            raise subprocess.CalledProcessError(1, "rclone")

        monkeypatch.setattr("rclone_manager.webui.subprocess.check_output", _raise)
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:file.txt") is False

    def test_dir_with_single_child_sharing_its_name_returns_true(self, monkeypatch):
        def fake_check_output(cmd, **kw):
            path = cmd[2]
            if path == "remote:/b":
                entries = [{"Path": "b", "Name": "b", "IsDir": False}]
            else:
                entries = [{"Path": "b", "Name": "b", "IsDir": True}]
            return json.dumps(entries).encode()

        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output", fake_check_output
        )
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:/b") is True

    def test_file_sharing_name_with_parent_dir_child_returns_false(self, monkeypatch):
        def fake_check_output(cmd, **kw):
            path = cmd[2]
            if path == "remote:/b":
                entries = [{"Path": "b", "Name": "b", "IsDir": False}]
            else:
                entries = [{"Path": "b", "Name": "b", "IsDir": False}]
            return json.dumps(entries).encode()

        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output", fake_check_output
        )
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:/b") is False


class TestDownloadRemoteFilesAsZip:
    def test_returns_zip_with_mixed_items(self, monkeypatch):
        from rclone_manager import webui

        def fake_run(cmd, check=True):
            src, dest = cmd[2], cmd[3]
            os.makedirs(dest, exist_ok=True)
            name = webui._remote_item_name(src)
            if os.path.basename(dest) == name:
                with open(os.path.join(dest, "child.txt"), "w") as f:
                    f.write("x")
            else:
                with open(os.path.join(dest, name), "w") as f:
                    f.write("x")

        monkeypatch.setattr(webui, "_is_remote_dir", lambda p: p.endswith("/dir"))
        monkeypatch.setattr("rclone_manager.webui.subprocess.run", fake_run)
        monkeypatch.setattr("rclone_manager.webui.st.warning", lambda *a, **kw: None)

        zip_buffer = webui.download_remote_files_as_zip(
            ["remote:/dir", "remote:file.txt"]
        )
        assert zip_buffer is not None
        with ZipFile(zip_buffer) as zf:
            assert sorted(zf.namelist()) == ["dir/child.txt", "file.txt"]

    def test_empty_selection_returns_none(self, monkeypatch):
        monkeypatch.setattr("rclone_manager.webui.st.warning", lambda *a, **kw: None)
        from rclone_manager.webui import download_remote_files_as_zip

        assert download_remote_files_as_zip([]) is None

    def test_rclone_failure_returns_none(self, monkeypatch):
        def _raise(*a, **kw):
            raise subprocess.CalledProcessError(1, "rclone")

        monkeypatch.setattr("rclone_manager.webui._is_remote_dir", lambda p: False)
        monkeypatch.setattr("rclone_manager.webui.subprocess.run", _raise)
        monkeypatch.setattr("rclone_manager.webui.st.error", lambda *a, **kw: None)
        from rclone_manager.webui import download_remote_files_as_zip

        assert download_remote_files_as_zip(["remote:file.txt"]) is None


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


class TestHiddenFileFiltering:
    def test_local_hidden_files_skipped_by_default(self, monkeypatch):
        fake_state = FakeSessionState({"show_hidden": False})
        monkeypatch.setattr("rclone_manager.webui.st.session_state", fake_state)
        from rclone_manager.webui import list_directory_contents

        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, ".hidden"), "w").close()
            open(os.path.join(tmpdir, "visible.txt"), "w").close()

            names = [c["name"] for c in list_directory_contents(tmpdir)]

        assert names == ["visible.txt"]

    def test_local_hidden_files_shown_when_enabled(self, monkeypatch):
        fake_state = FakeSessionState({"show_hidden": True})
        monkeypatch.setattr("rclone_manager.webui.st.session_state", fake_state)
        from rclone_manager.webui import list_directory_contents

        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, ".hidden"), "w").close()

            names = [c["name"] for c in list_directory_contents(tmpdir)]

        assert names == [".hidden"]

    def test_local_unreadable_items_are_skipped(self, monkeypatch):
        fake_state = FakeSessionState({"show_hidden": False})
        monkeypatch.setattr("rclone_manager.webui.st.session_state", fake_state)
        monkeypatch.setattr(
            "rclone_manager.webui.os.path.getsize",
            lambda *a, **kw: (_ for _ in ()).throw(OSError("gone")),
        )
        from rclone_manager.webui import list_directory_contents

        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "broken.txt"), "w").close()
            os.makedirs(os.path.join(tmpdir, "a_dir"), exist_ok=True)

            contents = list_directory_contents(tmpdir)

        assert [c["name"] for c in contents] == ["a_dir"]

    def test_remote_hidden_entries_skipped_by_default(self, monkeypatch):
        entries = [
            {"Name": ".hidden", "IsDir": False, "Size": 1},
            {"Name": "visible.txt", "IsDir": False, "Size": 2},
        ]
        monkeypatch.setattr("rclone_manager.webui.st.session_state", FakeSessionState({"show_hidden": False}))
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: json.dumps(entries).encode(),
        )
        from rclone_manager.webui import list_remote_directory_contents

        contents = list_remote_directory_contents("remote:/path")

        assert [c["name"] for c in contents] == ["visible.txt"]
        assert contents[0]["size"] == "2 bytes"
        assert contents[0]["modified"] == "-"

    def test_remote_hidden_entries_shown_when_enabled(self, monkeypatch):
        entries = [{"Name": ".hidden", "IsDir": True, "Size": 0}]
        monkeypatch.setattr("rclone_manager.webui.st.session_state", FakeSessionState({"show_hidden": True}))
        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output",
            lambda *a, **kw: json.dumps(entries).encode(),
        )
        from rclone_manager.webui import list_remote_directory_contents

        contents = list_remote_directory_contents("remote:/path")

        assert [c["name"] for c in contents] == [".hidden"]
        assert contents[0]["size"] == "-"


class TestIsRemoteDirParentLookup:
    def test_parent_listing_failure_returns_false(self, monkeypatch):
        def fake_check_output(cmd, **kw):
            if cmd[2] == "remote:/b":
                return json.dumps(
                    [{"Path": "b", "Name": "b", "IsDir": False}]
                ).encode()
            raise subprocess.CalledProcessError(1, "rclone")

        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output", fake_check_output
        )
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:/b") is False

    def test_parent_listing_bad_json_returns_false(self, monkeypatch):
        def fake_check_output(cmd, **kw):
            if cmd[2] == "remote:/b":
                return json.dumps(
                    [{"Path": "b", "Name": "b", "IsDir": False}]
                ).encode()
            return b"not json"

        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output", fake_check_output
        )
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:/b") is False

    def test_missing_parent_entry_returns_false(self, monkeypatch):
        def fake_check_output(cmd, **kw):
            if cmd[2] == "remote:/b":
                return json.dumps(
                    [{"Path": "b", "Name": "b", "IsDir": False}]
                ).encode()
            return json.dumps([{"Name": "other", "IsDir": True}]).encode()

        monkeypatch.setattr(
            "rclone_manager.webui.subprocess.check_output", fake_check_output
        )
        from rclone_manager.webui import _is_remote_dir

        assert _is_remote_dir("remote:/b") is False


class TestDownloadFilesAsZip:
    def test_empty_selection_returns_none(self, monkeypatch):
        messages = []
        monkeypatch.setattr(
            "rclone_manager.webui.st.warning", lambda *a, **kw: messages.append(a)
        )
        from rclone_manager.webui import download_files_as_zip

        assert download_files_as_zip([]) is None
        assert messages

    def test_zips_files_and_directories(self, monkeypatch):
        from rclone_manager.webui import download_files_as_zip

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "note.txt")
            with open(file_path, "w") as handle:
                handle.write("hello")
            dir_path = os.path.join(tmpdir, "folder")
            os.makedirs(dir_path)
            with open(os.path.join(dir_path, "inner.txt"), "w") as handle:
                handle.write("inner")

            zip_buffer = download_files_as_zip([file_path, dir_path])

        assert zip_buffer is not None
        with ZipFile(zip_buffer) as archive:
            assert sorted(archive.namelist()) == ["folder/inner.txt", "note.txt"]

    def test_missing_path_reports_error(self, monkeypatch):
        errors = []
        monkeypatch.setattr(
            "rclone_manager.webui.st.error", lambda *a, **kw: errors.append(a)
        )
        monkeypatch.setattr("rclone_manager.webui.st.warning", lambda *a, **kw: None)
        from rclone_manager.webui import download_files_as_zip

        assert download_files_as_zip(["/definitely/not/here"]) is None
        assert errors


class TestDownloadRemoteUnexpectedError:
    def test_unexpected_error_reports_and_returns_none(self, monkeypatch):
        errors = []
        monkeypatch.setattr(
            "rclone_manager.webui.st.error", lambda *a, **kw: errors.append(a)
        )
        monkeypatch.setattr(
            "rclone_manager.webui._is_remote_dir",
            lambda path: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        from rclone_manager.webui import download_remote_files_as_zip

        assert download_remote_files_as_zip(["remote:file.txt"]) is None
        assert errors
