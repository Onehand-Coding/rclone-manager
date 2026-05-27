import json
import os



class TestHelpers:
    def test_is_windows_returns_false_on_linux(self):
        from rclone_manager.status import _is_windows

        assert _is_windows() is False

    def test_is_mount_point_checks_ismount(self, monkeypatch):
        from rclone_manager.status import _is_mount_point

        monkeypatch.setattr(os.path, "ismount", lambda p: True)
        assert _is_mount_point("/mnt/test") is True

    def test_get_mount_base_uses_env_var(self, monkeypatch):
        from rclone_manager.status import _get_mount_base

        monkeypatch.setenv("RMAN_MOUNT_DIR", "/custom/status_mnt")
        assert _get_mount_base() == "/custom/status_mnt"

    def test_load_registry_returns_empty_when_no_file(self, monkeypatch):
        from rclone_manager.status import _load_registry

        monkeypatch.setenv("RMAN_MOUNT_DIR", "/nonexistent_status_test")
        assert _load_registry() == {}

    def test_load_sync_pairs_returns_empty_when_no_file(self, monkeypatch, tmp_path):
        import rclone_manager.config
        from rclone_manager import status

        monkeypatch.setattr(rclone_manager.config, "get_project_root", lambda: str(tmp_path))
        assert status._load_sync_pairs() == []

    def test_pending_transfers_returns_negative_when_no_rc(self):
        """When rc is unavailable, _pending_transfers returns -1."""
        from rclone_manager.status import _pending_transfers

        # Use an unused high port that will refuse connection
        result = _pending_transfers(5999)
        assert result == -1


class TestShowStatus:
    def test_shows_no_mounts_and_no_pairs(self, monkeypatch, test_output, tmp_path):
        import rclone_manager.config
        from rclone_manager import status

        monkeypatch.setattr(rclone_manager.config, "get_project_root", lambda: str(tmp_path))
        monkeypatch.setattr(status, "console", test_output)
        monkeypatch.setattr(status, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr(os.path, "exists", lambda p: True)
        monkeypatch.setattr(os, "listdir", lambda p: [])

        status.show_status()
        assert any("none active" in m for m in test_output.messages)
        assert any("none configured" in m for m in test_output.messages)

    def test_shows_active_mount(self, monkeypatch, test_output, tmp_path):
        import rclone_manager.config
        from rclone_manager import status

        mp = tmp_path / "testmount"
        mp.mkdir()
        registry_file = tmp_path / ".rc_ports.json"
        registry_file.write_text('{"testmount": 5572}')

        monkeypatch.setattr(rclone_manager.config, "get_project_root", lambda: str(tmp_path))
        monkeypatch.setattr(status, "console", test_output)
        monkeypatch.setattr(status, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr(os.path, "exists", lambda p: True)
        monkeypatch.setattr(os, "listdir", lambda p: ["testmount"])
        monkeypatch.setattr(os.path, "ismount", lambda p: p.endswith("testmount"))
        monkeypatch.setattr(status, "_pending_transfers", lambda port: 0)

        status.show_status()
        # Rich Table objects aren't rendered in TestOutput, check for active count
        assert any("active" in m for m in test_output.messages)

    def test_shows_sync_pairs(self, monkeypatch, test_output, tmp_path):
        import rclone_manager.config
        from rclone_manager import status

        configs = tmp_path / "configs"
        configs.mkdir()
        pair_file = configs / "sync-pairs.json"
        pair_file.write_text(json.dumps([
            {"name": "mypair", "mode": "upload_only", "local": "/src", "remote": "r:dst"}
        ]))

        monkeypatch.setattr(rclone_manager.config, "get_project_root", lambda: str(tmp_path))
        monkeypatch.setattr(status, "console", test_output)
        monkeypatch.setattr(status, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr(os.path, "exists", lambda p: True)
        monkeypatch.setattr(os, "listdir", lambda p: [])

        status.show_status()
        # Check that sync pairs section prints configured count
        assert any("configured" in m for m in test_output.messages)
