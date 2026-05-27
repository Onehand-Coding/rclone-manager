"""Comprehensive tests for rclone_manager.sync_pairs (target: 60%+ coverage)."""

import json

from rclone_manager.ports import CommandResult


# ---------------------------------------------------------------------------
# _config_path
# ---------------------------------------------------------------------------


class TestConfigPath:
    def test_returns_correct_path(self, monkeypatch):
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: "/project"
        )
        from rclone_manager.sync_pairs import _config_path

        assert _config_path() == "/project/configs/sync-pairs.json"


# ---------------------------------------------------------------------------
# _load_pairs
# ---------------------------------------------------------------------------


class TestLoadPairs:
    def test_returns_empty_when_no_file(self, monkeypatch):
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: "/nonexistent"
        )
        from rclone_manager.sync_pairs import _load_pairs

        assert _load_pairs() == []

    def test_parses_valid_json(self, monkeypatch, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text('[{"name": "test", "mode": "upload_only"}]')
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        from rclone_manager.sync_pairs import _load_pairs

        result = _load_pairs()
        assert len(result) == 1
        assert result[0]["name"] == "test"

    def test_returns_empty_on_invalid_json(self, monkeypatch, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text("not json")
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        from rclone_manager.sync_pairs import _load_pairs

        assert _load_pairs() == []

    def test_handles_generic_exception(self, monkeypatch, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text("{}")
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )

        def broken_open(*args, **kwargs):
            raise PermissionError("permission denied")

        monkeypatch.setattr("builtins.open", broken_open)
        from rclone_manager.sync_pairs import _load_pairs

        assert _load_pairs() == []


# ---------------------------------------------------------------------------
# _save_pairs
# ---------------------------------------------------------------------------


class TestSavePairs:
    def test_writes_json_file(self, monkeypatch, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        from rclone_manager.sync_pairs import _save_pairs

        pairs = [{"name": "p1", "mode": "upload_only"}]
        _save_pairs(pairs)
        file_path = configs / "sync-pairs.json"
        assert file_path.exists()
        assert json.loads(file_path.read_text()) == pairs


# ---------------------------------------------------------------------------
# _build_command — all 11 modes + edge cases
# ---------------------------------------------------------------------------


class TestBuildCommand:

    # ── local_to_remote modes ──

    def test_upload_only(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "upload_only",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "copy", "/a"]
        assert "r:b" in cmd

    def test_download_only(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "download_only",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "copy", "r:b"]
        assert "/a" in cmd

    def test_upload_delete(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "upload_delete",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "sync", "/a"]
        assert "r:b" in cmd

    def test_download_delete(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "download_delete",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "sync", "r:b"]
        assert "/a" in cmd

    def test_two_way_without_resync_done(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "two_way",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair)
        assert cmd[:4] == ["rclone", "bisync", "/a", "r:b"]
        assert "--resync" in cmd

    def test_two_way_with_resync_done(self, monkeypatch):
        monkeypatch.setattr("os.name", "posix")
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "two_way",
            "local": "/a", "remote": "r:b", "bisync_resync_done": True,
        }
        cmd = _build_command(pair)
        assert cmd[:4] == ["rclone", "bisync", "/a", "r:b"]
        assert "--resync" not in cmd

    def test_two_way_on_windows_always_resyncs(self, monkeypatch):
        # Patch os at the module level so pathlib isn't affected globally
        import rclone_manager.sync_pairs as _sp

        monkeypatch.setattr(_sp, "os", type("os", (), {"name": "nt"})())
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "two_way",
            "local": "/a", "remote": "r:b", "bisync_resync_done": True,
        }
        cmd = _build_command(pair)
        assert cmd[:4] == ["rclone", "bisync", "/a", "r:b"]
        assert "--resync" in cmd

    def test_move_to_remote(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "move_to_remote",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "move", "/a"]
        assert "r:b" in cmd

    def test_move_to_local(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "move_to_local",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "move", "r:b"]
        assert "/a" in cmd

    # ── remote_to_remote modes ──

    def test_remote_copy(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "remote_to_remote", "mode": "remote_copy",
            "source": "r1:a", "destination": "r2:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "copy", "r1:a"]
        assert "r2:b" in cmd

    def test_remote_sync_delete(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "remote_to_remote", "mode": "remote_sync_delete",
            "source": "r1:a", "destination": "r2:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "sync", "r1:a"]
        assert "r2:b" in cmd

    def test_remote_move(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "remote_to_remote", "mode": "remote_move",
            "source": "r1:a", "destination": "r2:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "move", "r1:a"]
        assert "r2:b" in cmd

    def test_remote_bisync_without_resync_done(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "remote_to_remote", "mode": "remote_bisync",
            "source": "r1:a", "destination": "r2:b",
        }
        cmd = _build_command(pair)
        assert cmd[:4] == ["rclone", "bisync", "r1:a", "r2:b"]
        assert "--resync" in cmd

    def test_remote_bisync_with_resync_done(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "remote_to_remote", "mode": "remote_bisync",
            "source": "r1:a", "destination": "r2:b", "bisync_resync_done": True,
        }
        cmd = _build_command(pair)
        assert cmd[:4] == ["rclone", "bisync", "r1:a", "r2:b"]
        assert "--resync" not in cmd

    # ── edge cases ──

    def test_unknown_mode_local_to_remote_returns_empty(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "nonexistent",
            "local": "/a", "remote": "r:b",
        }
        assert _build_command(pair) == []

    def test_unknown_mode_remote_to_remote_returns_empty(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "remote_to_remote", "mode": "nonexistent",
            "source": "r1:a", "destination": "r2:b",
        }
        assert _build_command(pair) == []

    def test_missing_type_defaults_to_local_to_remote(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "mode": "upload_only",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair)
        assert cmd[:3] == ["rclone", "copy", "/a"]
        assert "r:b" in cmd

    # ── dry_run ──

    def test_dry_run_adds_flag_standard(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "upload_only",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair, dry_run=True)
        assert "--dry-run" in cmd

    def test_dry_run_on_two_way(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "two_way",
            "local": "/a", "remote": "r:b",
        }
        cmd = _build_command(pair, dry_run=True)
        assert cmd[-1] == "--dry-run"
        assert "--resync" in cmd

    def test_dry_run_on_remote_bisync(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "remote_to_remote", "mode": "remote_bisync",
            "source": "r1:a", "destination": "r2:b",
        }
        cmd = _build_command(pair, dry_run=True)
        assert cmd[-1] == "--dry-run"
        assert "--resync" in cmd

    def test_dry_run_on_remote_copy(self):
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "remote_to_remote", "mode": "remote_copy",
            "source": "r1:a", "destination": "r2:b",
        }
        cmd = _build_command(pair, dry_run=True)
        assert "--dry-run" in cmd

    # ── filters ──

    def test_includes_filters(self, monkeypatch):
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args",
            lambda **kw: ["--exclude", "*.log", "--include", "important/*"],
        )
        from rclone_manager.sync_pairs import _build_command

        pair = {
            "name": "t", "type": "local_to_remote", "mode": "upload_only",
            "local": "/a", "remote": "r:b",
            "filters": {"exclude": ["*.log"], "include": ["important/*"]},
        }
        cmd = _build_command(pair)
        assert cmd == [
            "rclone", "copy", "/a", "r:b",
            "--exclude", "*.log", "--include", "important/*",
        ]


# ---------------------------------------------------------------------------
# _confirm_run
# ---------------------------------------------------------------------------


class TestConfirmRun:
    def test_destructive_shows_destructive_tag(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs.Confirm.ask", lambda *a, **kw: True)
        from rclone_manager.sync_pairs import _confirm_run

        pair = {
            "name": "test", "type": "local_to_remote", "mode": "upload_delete",
            "local": "/a", "remote": "r:b",
        }
        result = _confirm_run(pair)
        assert result is True
        assert any("DESTRUCTIVE" in m for m in test_output.messages)

    def test_safe_shows_safe_tag(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs.Confirm.ask", lambda *a, **kw: True)
        from rclone_manager.sync_pairs import _confirm_run

        pair = {
            "name": "test", "type": "local_to_remote", "mode": "upload_only",
            "local": "/a", "remote": "r:b",
        }
        result = _confirm_run(pair)
        assert result is True
        assert any("SAFE" in m for m in test_output.messages)

    def test_remote_to_remote_shows_source_destination(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs.Confirm.ask", lambda *a, **kw: True)
        from rclone_manager.sync_pairs import _confirm_run

        pair = {
            "name": "test", "type": "remote_to_remote", "mode": "remote_copy",
            "source": "r1:a", "destination": "r2:b",
        }
        result = _confirm_run(pair)
        assert result is True
        combined = " ".join(test_output.messages)
        assert "Remote\u2192Remote" in combined
        assert "Source" in combined
        assert "Destination" in combined

    def test_local_to_remote_shows_local_remote(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs.Confirm.ask", lambda *a, **kw: True)
        from rclone_manager.sync_pairs import _confirm_run

        pair = {
            "name": "test", "type": "local_to_remote", "mode": "upload_only",
            "local": "/a", "remote": "r:b",
        }
        result = _confirm_run(pair)
        assert result is True
        combined = " ".join(test_output.messages)
        assert "Local\u2192Remote" in combined
        assert "Local" in combined
        assert "Remote" in combined

    def test_returns_false_when_not_confirmed(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs.Confirm.ask", lambda *a, **kw: False)
        from rclone_manager.sync_pairs import _confirm_run

        pair = {
            "name": "test", "mode": "upload_only",
            "local": "/a", "remote": "r:b",
        }
        result = _confirm_run(pair)
        assert result is False


# ---------------------------------------------------------------------------
# sync_pairs_add
# ---------------------------------------------------------------------------


class TestSyncPairsAdd:
    def test_empty_name_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        test_output.add_input_response("")
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()

    def test_duplicate_name_shows_error(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text('[{"name": "mypair", "mode": "upload_only"}]')
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        test_output.add_input_response("mypair")
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert any("already exists" in m for m in test_output.messages)

    def test_cancel_at_type_selection(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        test_output.add_input_response("mypair")
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: None
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert not (configs / "sync-pairs.json").exists()

    def test_invalid_local_path_rejected(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes", lambda: ["gdrive"]
        )
        test_output.add_input_response("mypair")
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: "Local \u2192 Remote \u2014 Sync local folder with remote storage",
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_local_file_system", lambda **kw: None
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert any("Invalid local path" in m for m in test_output.messages)

    def test_no_remotes_returns_early(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes", lambda: []
        )
        test_output.add_input_response("mypair")
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: "Local \u2192 Remote \u2014 Sync local folder with remote storage",
        )
        local_dir = tmp_path / "local_folder"
        local_dir.mkdir()
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_local_file_system",
            lambda **kw: str(local_dir),
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert not (configs / "sync-pairs.json").exists()

    def test_local_to_remote_full_flow(
        self, monkeypatch, test_output, tmp_path, fake_runner
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes", lambda: ["gdrive"]
        )

        test_output.add_input_response("backup_job")

        choose_results = iter([
            "Local \u2192 Remote \u2014 Sync local folder with remote storage",
            "gdrive",
            "Download Only \u2014 Copy remote \u2192 local (no deletions)",
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )

        local_dir = tmp_path / "local_folder"
        local_dir.mkdir()
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_local_file_system",
            lambda **kw: str(local_dir),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_remote_file_system",
            lambda *a, **kw: "gdrive:/backup",
        )
        test_output.add_input_response("")
        test_output.add_input_response("")

        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()

        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert len(saved) == 1
        assert saved[0]["name"] == "backup_job"
        assert saved[0]["type"] == "local_to_remote"
        assert saved[0]["mode"] == "download_only"
        assert saved[0]["local"] == str(local_dir)
        assert saved[0]["remote"] == "gdrive:/backup"
        assert saved[0]["bisync_resync_done"] is False
        assert any("added" in m for m in test_output.messages)

    def test_remote_to_remote_full_flow(
        self, monkeypatch, test_output, tmp_path
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes",
            lambda: ["gdrive", "mega"],
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_remote_file_system",
            lambda *a, **kw: f"{a[0]}:/path",
        )

        test_output.add_input_response("cloud_sync")

        choose_results = iter([
            "Remote \u2192 Remote \u2014 Sync between two remote storages (server-side when possible)",
            "gdrive",
            "mega",
            "Remote Copy \u2014 Copy remote1 \u2192 remote2 (no deletions, server-side when possible)",
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )
        test_output.add_input_response("")
        test_output.add_input_response("")

        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()

        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert len(saved) == 1
        assert saved[0]["name"] == "cloud_sync"
        assert saved[0]["type"] == "remote_to_remote"
        assert saved[0]["mode"] == "remote_copy"
        assert saved[0]["source"] == "gdrive:/path"
        assert saved[0]["destination"] == "mega:/path"

    def test_filter_input_parsing(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes", lambda: ["gdrive"]
        )

        test_output.add_input_response("filtered_job")

        choose_results = iter([
            "Local \u2192 Remote \u2014 Sync local folder with remote storage",
            "gdrive",
            "Upload Only \u2014 Copy local \u2192 remote (no deletions)",
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )

        local_dir = tmp_path / "local_folder"
        local_dir.mkdir()
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_local_file_system",
            lambda **kw: str(local_dir),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_remote_file_system",
            lambda *a, **kw: "gdrive:/backup",
        )

        test_output.add_input_response("*.log, temp/, drafts/")
        test_output.add_input_response("important/*, projects/*.pdf")

        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()

        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert saved[0]["filters"]["exclude"] == ["*.log", "temp/", "drafts/"]
        assert saved[0]["filters"]["include"] == ["important/*", "projects/*.pdf"]

    # ── edge cases that exit early at various steps ──

    def test_remote_name_not_selected(self, monkeypatch, test_output, tmp_path):
        """choose_from_list returns None when selecting remote name → line 264."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes", lambda: ["gdrive"]
        )
        test_output.add_input_response("mypair")
        local_dir = tmp_path / "local_folder"
        local_dir.mkdir()
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_local_file_system",
            lambda **kw: str(local_dir),
        )
        choose_results = iter([
            "Local \u2192 Remote \u2014 Sync local folder with remote storage",
            None,  # remote name selection cancelled
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert not (configs / "sync-pairs.json").exists()

    def test_invalid_remote_path_local_to_remote(
        self, monkeypatch, test_output, tmp_path
    ):
        """navigate_remote_file_system returns None → lines 271-272."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes", lambda: ["gdrive"]
        )
        test_output.add_input_response("mypair")
        local_dir = tmp_path / "local_folder"
        local_dir.mkdir()
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_local_file_system",
            lambda **kw: str(local_dir),
        )
        choose_results = iter([
            "Local \u2192 Remote \u2014 Sync local folder with remote storage",
            "gdrive",
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_remote_file_system",
            lambda *a, **kw: None,
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert any("Invalid remote path" in m for m in test_output.messages)
        assert not (configs / "sync-pairs.json").exists()

    def test_remote_to_remote_no_remotes(
        self, monkeypatch, test_output, tmp_path
    ):
        """list_rclone_remotes returns [] after type selection → line 284."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes", lambda: []
        )
        test_output.add_input_response("mypair")
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: "Remote \u2192 Remote \u2014 Sync between two remote storages (server-side when possible)",
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert not (configs / "sync-pairs.json").exists()

    def test_remote_to_remote_invalid_source_path(
        self, monkeypatch, test_output, tmp_path
    ):
        """navigate_remote_file_system returns None for source → lines 294-295."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes",
            lambda: ["gdrive", "mega"],
        )
        test_output.add_input_response("mypair")
        choose_results = iter([
            "Remote \u2192 Remote \u2014 Sync between two remote storages (server-side when possible)",
            "gdrive",
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_remote_file_system",
            lambda *a, **kw: None,
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert any("Invalid source path" in m for m in test_output.messages)
        assert not (configs / "sync-pairs.json").exists()

    def test_remote_to_remote_dest_not_selected(
        self, monkeypatch, test_output, tmp_path
    ):
        """choose_from_list returns None for destination remote → line 303."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes",
            lambda: ["gdrive", "mega"],
        )
        test_output.add_input_response("mypair")
        choose_results = iter([
            "Remote \u2192 Remote \u2014 Sync between two remote storages (server-side when possible)",
            "gdrive",
            None,  # destination remote selection cancelled
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_remote_file_system",
            lambda *a, **kw: f"{a[0]}:/path",
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert not (configs / "sync-pairs.json").exists()

    def test_remote_to_remote_invalid_dest_path(
        self, monkeypatch, test_output, tmp_path
    ):
        """navigate_remote_file_system returns None for dest → lines 310-311."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes",
            lambda: ["gdrive", "mega"],
        )
        test_output.add_input_response("mypair")
        # source path succeeds, but dest path returns None
        nav_results = iter(["gdrive:/src", None])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_remote_file_system",
            lambda *a, **kw: next(nav_results),
        )
        choose_results = iter([
            "Remote \u2192 Remote \u2014 Sync between two remote storages (server-side when possible)",
            "gdrive",
            "mega",
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert any("Invalid destination path" in m for m in test_output.messages)
        assert not (configs / "sync-pairs.json").exists()

    def test_mode_selection_cancelled(self, monkeypatch, test_output, tmp_path):
        """choose_from_list returns None at mode selection → line 331."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes", lambda: ["gdrive"]
        )
        test_output.add_input_response("mypair")
        local_dir = tmp_path / "local_folder"
        local_dir.mkdir()
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_local_file_system",
            lambda **kw: str(local_dir),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_remote_file_system",
            lambda *a, **kw: "gdrive:/backup",
        )
        choose_results = iter([
            "Local \u2192 Remote \u2014 Sync local folder with remote storage",
            "gdrive",
            None,  # mode selection cancelled
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert not (configs / "sync-pairs.json").exists()

    def test_local_path_must_be_directory(self, monkeypatch, test_output, tmp_path):
        """navigate_local_file_system returns string but path not a dir → lines 255-256."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        test_output.add_input_response("mypair")
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: "Local \u2192 Remote \u2014 Sync local folder with remote storage",
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.navigate_local_file_system",
            lambda **kw: "/nonexistent/path",
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert any("must be a directory" in m for m in test_output.messages)
        assert not (configs / "sync-pairs.json").exists()

    def test_remote_to_remote_source_remote_as_list(
        self, monkeypatch, test_output, tmp_path
    ):
        """choose_from_list returns a list for source remote → line 287."""
        configs = tmp_path / "configs"
        configs.mkdir()
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.list_rclone_remotes",
            lambda: ["gdrive", "mega"],
        )
        test_output.add_input_response("mypair")
        choose_results = iter([
            "Remote \u2192 Remote \u2014 Sync between two remote storages (server-side when possible)",
            ["gdrive"],  # source_remote as list
        ])
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: next(choose_results),
        )
        from rclone_manager.sync_pairs import sync_pairs_add

        sync_pairs_add()
        assert not (configs / "sync-pairs.json").exists()


# ---------------------------------------------------------------------------
# sync_pairs_list
# ---------------------------------------------------------------------------


class TestSyncPairsList:
    def test_prints_when_empty(self, monkeypatch, test_output):
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: "/nope"
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        from rclone_manager.sync_pairs import sync_pairs_list

        sync_pairs_list()
        assert any("No sync pairs" in m for m in test_output.messages)

    def test_displays_populated_table(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1",
                "type": "local_to_remote",
                "mode": "upload_delete",
                "local": "/src",
                "remote": "r:dst",
                "filters": {"exclude": ["*.tmp"], "include": ["*.doc"]},
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        from rclone_manager.sync_pairs import sync_pairs_list

        sync_pairs_list()
        # Table is rendered via Rich's console — TestOutput captures str(table)
        # which doesn't render Rich Table contents; verify no empty-state message
        assert not any("No sync pairs" in m for m in test_output.messages)

    def test_displays_remote_to_remote_pair(self, monkeypatch, test_output, tmp_path):
        """Verify remote_to_remote pairs render without error in list table."""
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "r2r",
                "type": "remote_to_remote",
                "mode": "remote_copy",
                "source": "r1:a",
                "destination": "r2:b",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        from rclone_manager.sync_pairs import sync_pairs_list

        sync_pairs_list()
        assert not any("No sync pairs" in m for m in test_output.messages)


# ---------------------------------------------------------------------------
# sync_pairs_run
# ---------------------------------------------------------------------------


class TestSyncPairsRun:
    def test_prints_when_empty(self, monkeypatch, test_output):
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: "/nope"
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run()
        assert any("No sync pairs" in m for m in test_output.messages)

    def test_run_no_selection_returns_early(self, monkeypatch, tmp_path, test_output):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
                "local": "/src", "remote": "r:dst",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: None
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run()

    def test_dry_run_select_all(
        self, monkeypatch, tmp_path, fake_runner, test_output
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
                "local": "/src", "remote": "r:dst",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs._runner", fake_runner)
        fake_runner.add_response(CommandResult(0, stdout="dry output"))
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "All"
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run(dry_run=True)
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "rclone" in last_cmd
        assert "copy" in last_cmd
        assert "--dry-run" in last_cmd

    def test_dry_run_unknown_mode(
        self, monkeypatch, tmp_path, fake_runner, test_output
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "bad_mode",
                "local": "/src", "remote": "r:dst",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs._runner", fake_runner)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "All"
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run(dry_run=True)
        assert any("Unknown mode" in m for m in test_output.messages)

    def test_run_cancels_when_not_confirmed(
        self, monkeypatch, tmp_path, test_output
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
                "local": "/src", "remote": "r:dst",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "All"
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._confirm_run", lambda pair: False
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run()
        assert any("Skipped" in m for m in test_output.messages)

    def test_select_specific_pair(
        self, monkeypatch, tmp_path, fake_runner, test_output
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
                "local": "/src", "remote": "r:dst",
            },
            {
                "name": "p2", "type": "local_to_remote", "mode": "download_only",
                "local": "/src", "remote": "r:dst",
            },
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs._runner", fake_runner)
        fake_runner.add_response(CommandResult(0, stdout="ok"))
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._confirm_run", lambda pair: True
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._run_rclone_with_stats",
            lambda *a: (0, []),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "p1"
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run()
        assert any("completed" in m for m in test_output.messages)

    def test_run_failure_reported(
        self, monkeypatch, tmp_path, fake_runner, test_output
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
                "local": "/src", "remote": "r:dst",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs._runner", fake_runner)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._confirm_run", lambda pair: True
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._run_rclone_with_stats",
            lambda *a: (1, ["sync error"]),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "All"
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run()
        assert any("failed" in m for m in test_output.messages)

    def test_bisync_resync_tracking_success(
        self, monkeypatch, tmp_path, test_output
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "bisync_pair", "type": "local_to_remote", "mode": "two_way",
                "local": "/src", "remote": "r:dst", "bisync_resync_done": False,
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._confirm_run", lambda pair: True
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._run_rclone_with_stats",
            lambda *a: (0, []),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "All"
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run()
        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert saved[0]["bisync_resync_done"] is True

    def test_bisync_resync_tracking_failure(
        self, monkeypatch, tmp_path, test_output
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "bisync_pair", "type": "local_to_remote", "mode": "two_way",
                "local": "/src", "remote": "r:dst", "bisync_resync_done": True,
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._confirm_run", lambda pair: True
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._run_rclone_with_stats",
            lambda *a: (1, ["error"]),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "All"
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run()
        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert saved[0]["bisync_resync_done"] is False

    def test_select_multiple_pairs(
        self, monkeypatch, tmp_path, test_output
    ):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
                "local": "/src1", "remote": "r:dst1",
            },
            {
                "name": "p2", "type": "local_to_remote", "mode": "download_only",
                "local": "/src2", "remote": "r:dst2",
            },
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._confirm_run", lambda pair: True
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs._run_rclone_with_stats",
            lambda *a: (0, []),
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: ["p1", "p2"],
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run()
        completed = [m for m in test_output.messages if "completed" in m]
        assert len(completed) == 2

    def test_dry_run_shows_stderr(
        self, monkeypatch, tmp_path, fake_runner, test_output
    ):
        """Dry-run reports stderr output when present."""
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
                "local": "/src", "remote": "r:dst",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr("rclone_manager.sync_pairs._runner", fake_runner)
        fake_runner.add_response(
            CommandResult(0, stdout="ok", stderr="some warning")
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "All"
        )
        monkeypatch.setattr(
            "rclone_manager.config.merge_filter_args", lambda **kw: []
        )
        from rclone_manager.sync_pairs import sync_pairs_run

        sync_pairs_run(dry_run=True)
        assert any("some warning" in m for m in test_output.messages)


# ---------------------------------------------------------------------------
# sync_pairs_remove
# ---------------------------------------------------------------------------


class TestSyncPairsRemove:
    def test_prints_when_empty(self, monkeypatch, test_output):
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: "/nope"
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        from rclone_manager.sync_pairs import sync_pairs_remove

        sync_pairs_remove()
        assert any("No sync pairs" in m for m in test_output.messages)

    def test_cancel_at_selection(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: None
        )
        from rclone_manager.sync_pairs import sync_pairs_remove

        sync_pairs_remove()
        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert len(saved) == 1

    def test_cancel_removal_at_confirm(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.Confirm.ask", lambda *a, **kw: False
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "p1"
        )
        from rclone_manager.sync_pairs import sync_pairs_remove

        sync_pairs_remove()
        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert len(saved) == 1  # unchanged
        assert not any("Removed" in m for m in test_output.messages)

    def test_confirm_removal(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(
            json.dumps(
                [
                    {
                        "name": "p1",
                        "type": "local_to_remote",
                        "mode": "upload_only",
                    },
                    {
                        "name": "p2",
                        "type": "local_to_remote",
                        "mode": "download_only",
                    },
                ]
            )
        )
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.Confirm.ask", lambda *a, **kw: True
        )
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "p1"
        )
        from rclone_manager.sync_pairs import sync_pairs_remove

        sync_pairs_remove()
        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert len(saved) == 1
        assert saved[0]["name"] == "p2"
        assert any("Removed" in m for m in test_output.messages)

    def test_handle_missing_pair_name(self, monkeypatch, test_output, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {
                "name": "p1", "type": "local_to_remote", "mode": "upload_only",
            }
        ]))
        monkeypatch.setattr(
            "rclone_manager.config.get_project_root", lambda: str(tmp_path)
        )
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list",
            lambda *a, **kw: "nonexistent",
        )
        from rclone_manager.sync_pairs import sync_pairs_remove

        sync_pairs_remove()
        saved = json.loads((configs / "sync-pairs.json").read_text())
        assert len(saved) == 1


# ---------------------------------------------------------------------------
# sync_pairs  (dispatch)
# ---------------------------------------------------------------------------


class TestSyncPairsDispatch:
    def test_dispatches_to_add(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "add"
        )
        called = []
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.sync_pairs_add", lambda: called.append("add")
        )
        from rclone_manager.sync_pairs import sync_pairs

        sync_pairs()
        assert "add" in called

    def test_dispatches_to_list(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "list"
        )
        called = []
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.sync_pairs_list", lambda: called.append("list")
        )
        from rclone_manager.sync_pairs import sync_pairs

        sync_pairs()
        assert "list" in called

    def test_dispatches_to_run(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "run"
        )
        called = []
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.sync_pairs_run", lambda: called.append("run")
        )
        from rclone_manager.sync_pairs import sync_pairs

        sync_pairs()
        assert "run" in called

    def test_dispatches_to_remove(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: "remove"
        )
        called = []
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.sync_pairs_remove",
            lambda: called.append("remove"),
        )
        from rclone_manager.sync_pairs import sync_pairs

        sync_pairs()
        assert "remove" in called

    def test_no_action_returns_early(self, monkeypatch, test_output):
        monkeypatch.setattr("rclone_manager.sync_pairs.console", test_output)
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.choose_from_list", lambda *a, **kw: None
        )
        dispatched = []
        monkeypatch.setattr(
            "rclone_manager.sync_pairs.sync_pairs_add",
            lambda: dispatched.append("add"),
        )
        from rclone_manager.sync_pairs import sync_pairs

        sync_pairs()
        assert len(dispatched) == 0
