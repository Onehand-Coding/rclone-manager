import os

from rclone_manager.ports import CommandResult


class TestHelpers:
    def test_is_windows_returns_false_on_linux(self):
        from rclone_manager.mount import _is_windows

        assert _is_windows() is False

    def test_get_mount_base_uses_env_var(self, monkeypatch):
        from rclone_manager.mount import _get_mount_base

        monkeypatch.setenv("MOUNT_DIR", "/custom/mnt")
        assert _get_mount_base() == "/custom/mnt"

    def test_get_mount_base_defaults(self):
        from rclone_manager.mount import _get_mount_base

        path = _get_mount_base()
        assert path == os.path.expanduser("~/mnt")

    def test_find_free_port_returns_start_when_scan_range_exhausted(self, monkeypatch):
        from rclone_manager.mount import _find_free_port

        port = _find_free_port(5999)
        assert port == 5999

    def test_is_unsupported_detects_gphotos(self):
        from rclone_manager.mount import _is_unsupported

        assert _is_unsupported("gphotos", "google photos")

    def test_is_unsupported_allows_drive(self):
        from rclone_manager.mount import _is_unsupported

        assert not _is_unsupported("mydrive", "drive")

    def test_registry_path_uses_mount_base(self, monkeypatch):
        from rclone_manager.mount import _registry_path

        monkeypatch.setenv("MOUNT_DIR", "/tmp/rman_test")
        assert _registry_path() == "/tmp/rman_test/.rc_ports.json"

    def test_load_registry_returns_empty_when_no_file(self, monkeypatch):
        from rclone_manager.mount import _load_registry

        monkeypatch.setenv("MOUNT_DIR", "/nonexistent_path_xyz")
        assert _load_registry() == {}

    def test_save_and_load_registry(self, monkeypatch, tmp_path):
        from rclone_manager.mount import _load_registry, _save_registry

        monkeypatch.setenv("MOUNT_DIR", str(tmp_path))
        _save_registry({"test": {"rc_port": 5572, "pid": 1234}})
        data = _load_registry()
        assert data["test"]["rc_port"] == 5572

    def test_remove_from_registry(self, monkeypatch, tmp_path):
        from rclone_manager.mount import _load_registry, _save_registry, _remove_from_registry

        monkeypatch.setenv("MOUNT_DIR", str(tmp_path))
        _save_registry({"keep": {"rc_port": 1}, "remove": {"rc_port": 2}})
        _remove_from_registry("remove")
        data = _load_registry()
        assert "keep" in data
        assert "remove" not in data

    def test_get_registry_entry_old_format(self):
        from rclone_manager.mount import _get_registry_entry

        port, pid = _get_registry_entry({"mnt": 5572}, "mnt")
        assert port == 5572
        assert pid is None

    def test_get_registry_entry_new_format(self):
        from rclone_manager.mount import _get_registry_entry

        entry = {"rc_port": 5572, "pid": 999}
        port, pid = _get_registry_entry({"mnt": entry}, "mnt")
        assert port == 5572
        assert pid == 999


class TestMountRemote:
    def test_checks_fuse_available(self, monkeypatch, test_output, fake_runner):
        """When no fuse is available, prints error and returns."""
        from rclone_manager import mount

        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "shutil", type("s", (), {"which": lambda *a: None})())
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)

        mount.mount_remote()
        assert any("FUSE not available" in m for m in test_output.messages)

    def test_no_remotes_exits_early(self, monkeypatch, test_output, fake_runner):
        from rclone_manager import mount

        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "shutil", type("s", (), {"which": lambda *a: "/usr/bin/fusermount"})())
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        monkeypatch.setattr(mount, "list_rclone_remotes", lambda: [])

        mount.mount_remote()
        assert any("No rclone remotes" in m for m in test_output.messages)


class TestUnmountRemote:
    def test_no_mounts_dir(self, monkeypatch, test_output, fake_runner):
        from rclone_manager import mount

        monkeypatch.setattr(mount, "_get_mount_base", lambda: "/nonexistent_mount_base")
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)

        mount.unmount_remote()
        assert any("No mounts directory" in m for m in test_output.messages)

    def test_unmount_calls_fusermount(self, monkeypatch, tmp_path, test_output, fake_runner):
        from rclone_manager import mount

        mp = tmp_path / "testremote"
        mp.mkdir()
        registry_file = tmp_path / ".rc_ports.json"
        registry_file.write_text('{"testremote": {"rc_port": 5572, "pid": 999}}')

        monkeypatch.setattr(mount, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        monkeypatch.setattr(mount, "_unmount_via_rc", lambda *a: False)
        monkeypatch.setattr(mount, "_fusermount_cmd", lambda: "fusermount")
        monkeypatch.setattr(os.path, "ismount", lambda p: p == str(mp))
        monkeypatch.setattr(os, "listdir", lambda p: ["testremote"])

        monkeypatch.setattr(
            "rclone_manager.mount.choose_from_list", lambda *a, **kw: "All"
        )

        # Responses: rc_vfs_stats, rc unmount, fusermount -u, lazy fusermount -uz
        fake_runner.add_response(CommandResult(1, stdout="{}"))
        fake_runner.add_response(CommandResult(1, stderr="unmount failed"))
        fake_runner.add_response(CommandResult(1, stderr="device or resource busy"))
        fake_runner.add_response(CommandResult(0))

        mount.unmount_remote()
        assert len(fake_runner.commands) >= 1
        last_cmd = fake_runner.commands[-1]
        assert "fusermount" in last_cmd
        assert "-uz" in last_cmd
