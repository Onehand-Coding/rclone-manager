import json

from rclone_manager.ports import CommandResult


class TestLoadPairs:
    def test_returns_empty_when_no_file(self, monkeypatch):
        import rclone_manager.config
        from rclone_manager import sync_pairs

        monkeypatch.setattr(
            rclone_manager.config, "get_project_root", lambda: "/nonexistent"
        )
        assert sync_pairs._load_pairs() == []

    def test_parses_valid_json(self, monkeypatch, tmp_path):
        import rclone_manager.config
        from rclone_manager import sync_pairs

        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text('[{"name": "test", "mode": "upload_only"}]')
        monkeypatch.setattr(
            rclone_manager.config, "get_project_root", lambda: str(tmp_path)
        )
        result = sync_pairs._load_pairs()
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_returns_empty_on_invalid_json(self, monkeypatch, tmp_path):
        import rclone_manager.config
        from rclone_manager import sync_pairs

        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text("not json")
        monkeypatch.setattr(
            rclone_manager.config, "get_project_root", lambda: str(tmp_path)
        )
        assert sync_pairs._load_pairs() == []


class TestSavePairs:
    def test_writes_json_file(self, monkeypatch, tmp_path):
        import rclone_manager.config
        from rclone_manager import sync_pairs

        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            rclone_manager.config, "get_project_root", lambda: str(tmp_path)
        )
        pairs = [{"name": "p1", "mode": "upload_only"}]
        sync_pairs._save_pairs(pairs)
        file_path = configs / "sync-pairs.json"
        assert file_path.exists()
        data = json.loads(file_path.read_text())
        assert data == pairs


class TestBuildCommand:
    def test_upload_only(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "test",
            "type": "local_to_remote",
            "mode": "upload_only",
            "local": "/local/path",
            "remote": "remote:backup",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "copy", "/local/path"]
        assert "remote:backup" in cmd

    def test_download_delete(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "test",
            "type": "local_to_remote",
            "mode": "download_delete",
            "local": "/local/path",
            "remote": "remote:backup",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "sync", "remote:backup"]
        assert "/local/path" in cmd

    def test_remote_copy(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "test",
            "type": "remote_to_remote",
            "mode": "remote_copy",
            "source": "remote1:src",
            "destination": "remote2:dst",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "copy", "remote1:src"]
        assert "remote2:dst" in cmd

    def test_dry_run_adds_flag(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "test",
            "type": "local_to_remote",
            "mode": "upload_only",
            "local": "/a",
            "remote": "r:b",
        }
        cmd = _build_command(pair, dry_run=True)
        assert "--dry-run" in cmd

    def test_unknown_mode_returns_empty(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "test",
            "type": "local_to_remote",
            "mode": "nonexistent",
            "local": "/a",
            "remote": "r:b",
        }
        assert _build_command(pair) == []


class TestListPairs:
    def test_prints_message_when_empty(self, monkeypatch, test_output):
        import rclone_manager.config
        from rclone_manager import sync_pairs

        monkeypatch.setattr(rclone_manager.config, "get_project_root", lambda: "/nope")
        monkeypatch.setattr(sync_pairs, "console", test_output)
        sync_pairs.sync_pairs_list()
        assert any("No sync pairs" in m for m in test_output.messages)


class TestRemovePairs:
    def test_prints_message_when_empty(self, monkeypatch, test_output):
        import rclone_manager.config
        from rclone_manager import sync_pairs

        monkeypatch.setattr(rclone_manager.config, "get_project_root", lambda: "/nope")
        monkeypatch.setattr(sync_pairs, "console", test_output)
        sync_pairs.sync_pairs_remove()
        assert any("No sync pairs" in m for m in test_output.messages)


class TestRunPairs:
    def test_prints_message_when_empty(self, monkeypatch, test_output):
        import rclone_manager.config
        from rclone_manager import sync_pairs

        monkeypatch.setattr(rclone_manager.config, "get_project_root", lambda: "/nope")
        monkeypatch.setattr(sync_pairs, "console", test_output)
        sync_pairs.sync_pairs_run()
        assert any("No sync pairs" in m for m in test_output.messages)

    def test_dry_run_executes_runner(self, monkeypatch, tmp_path, fake_runner):
        import rclone_manager.config
        from rclone_manager import sync_pairs

        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1",
                "type": "local_to_remote",
                "mode": "upload_only",
                "local": "/src",
                "remote": "r:dst",
            }
        ]))
        monkeypatch.setattr(
            rclone_manager.config, "get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr(sync_pairs, "_runner", fake_runner)
        fake_runner.add_response(CommandResult(0, stdout="dry ok"))

        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "All"
        )

        sync_pairs.sync_pairs_run(dry_run=True)
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "rclone" in last_cmd
        assert "copy" in last_cmd
