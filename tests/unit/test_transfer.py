import os

from rclone_manager.ports import CommandResult


class TestUploadBackup:
    def test_no_local_selection_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_local_file_system",
            lambda purpose=None, **kw: None,
        )

        from rclone_manager.transfer import upload_backup

        upload_backup()

    def test_no_remotes_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_local_file_system",
            lambda purpose=None, **kw: "/local/file.txt",
        )
        monkeypatch.setattr("rclone_manager.transfer.list_rclone_remotes", lambda: [])

        from rclone_manager.transfer import upload_backup

        upload_backup()

    def _setup_input(self, test_output):
        test_output.add_input_response("")

    def test_upload_single_file(self, monkeypatch, test_output, tmp_path):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_local_file_system",
            lambda purpose=None, **kw: str(tmp_path / "test.txt"),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: "myremote:/dest",
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.choose_from_list", lambda *a, **kw: "myremote"
        )
        monkeypatch.setattr(
            "rclone_manager.transfer._run_rclone_with_stats",
            lambda label, cmd, **kw: (0, []),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.get_project_root", lambda: str(tmp_path)
        )
        self._setup_input(test_output)

        from rclone_manager.transfer import upload_backup

        upload_backup()

    def test_upload_with_overwrite(self, monkeypatch, test_output, tmp_path):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_local_file_system",
            lambda purpose=None, **kw: str(tmp_path / "test.txt"),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: "myremote:/dest",
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.choose_from_list", lambda *a, **kw: "myremote"
        )
        monkeypatch.setattr(
            "rclone_manager.transfer._run_rclone_with_stats",
            lambda label, cmd, **kw: (0, []),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.get_project_root", lambda: str(tmp_path)
        )
        self._setup_input(test_output)

        from rclone_manager.transfer import upload_backup

        upload_backup(overwrite=True)

    def test_upload_failure_reported(self, monkeypatch, test_output, tmp_path):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_local_file_system",
            lambda purpose=None, **kw: str(tmp_path / "test.txt"),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: "myremote:/dest",
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.choose_from_list", lambda *a, **kw: "myremote"
        )
        monkeypatch.setattr(
            "rclone_manager.transfer._run_rclone_with_stats",
            lambda label, cmd, **kw: (1, ["Error: connection failed"]),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.get_project_root", lambda: str(tmp_path)
        )
        self._setup_input(test_output)

        from rclone_manager.transfer import upload_backup

        upload_backup()
        assert any("Upload failed" in m for m in test_output.messages)


class TestDownloadBackup:
    def _setup_input(self, test_output):
        test_output.add_input_response("")

    def test_no_remotes_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr("rclone_manager.transfer.list_rclone_remotes", lambda: [])

        from rclone_manager.transfer import download_backup

        download_backup()

    def test_no_remote_selection_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.transfer.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.choose_from_list", lambda *a, **kw: None
        )

        from rclone_manager.transfer import download_backup

        download_backup()

    def test_download_single_file(self, monkeypatch, test_output, tmp_path):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.transfer.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: "myremote:/file.txt",
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_local_file_system",
            lambda purpose=None, **kw: str(tmp_path),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.choose_from_list", lambda *a, **kw: "myremote"
        )
        monkeypatch.setattr(
            "rclone_manager.transfer._run_rclone_with_stats",
            lambda label, cmd, **kw: (0, []),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.get_project_root", lambda: str(tmp_path)
        )
        self._setup_input(test_output)

        from rclone_manager.transfer import download_backup

        download_backup()

    def test_download_failure_reported(self, monkeypatch, test_output, tmp_path):
        monkeypatch.setattr("rclone_manager.transfer.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.transfer.list_rclone_remotes", lambda: ["myremote"]
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_remote_file_system",
            lambda remote, purpose=None, **kw: "myremote:/file.txt",
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.navigate_local_file_system",
            lambda purpose=None, **kw: str(tmp_path),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.choose_from_list", lambda *a, **kw: "myremote"
        )
        monkeypatch.setattr(
            "rclone_manager.transfer._run_rclone_with_stats",
            lambda label, cmd, **kw: (1, ["Error: not found"]),
        )
        monkeypatch.setattr(
            "rclone_manager.transfer.get_project_root", lambda: str(tmp_path)
        )
        self._setup_input(test_output)

        from rclone_manager.transfer import download_backup

        download_backup()
        assert any("Download failed" in m for m in test_output.messages)
