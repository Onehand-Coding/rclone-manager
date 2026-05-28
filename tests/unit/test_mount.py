import os
import sys

from rclone_manager.ports import CommandResult


class TestHelpers:
    def test_is_windows_returns_true_on_windows(self):
        from rclone_manager.mount import _is_windows

        assert _is_windows() is (sys.platform == "win32")

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

    def test_find_free_port_finds_open_port(self, monkeypatch):
        from rclone_manager.mount import _find_free_port
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        assert _find_free_port(port) == port
        sock.close()

    def test_is_unsupported_detects_gphotos(self):
        from rclone_manager.mount import _is_unsupported

        assert _is_unsupported("gphotos", "google photos")

    def test_is_unsupported_allows_drive(self):
        from rclone_manager.mount import _is_unsupported

        assert not _is_unsupported("mydrive", "drive")

    def test_registry_path_uses_mount_base(self, monkeypatch):
        from rclone_manager.mount import _registry_path

        import os as os_module
        monkeypatch.setenv("MOUNT_DIR", "/tmp/rman_test")
        expected = os_module.path.join("/tmp/rman_test", ".rc_ports.json")
        assert _registry_path() == expected

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

    def test_finalize_unmount_removes_dir_and_registry(self, monkeypatch, tmp_path):
        from rclone_manager.mount import _finalize_unmount, _save_registry, _load_registry

        mp = tmp_path / "mymount"
        mp.mkdir()
        monkeypatch.setenv("MOUNT_DIR", str(tmp_path))
        _save_registry({"mymount": {"rc_port": 5572}})

        _finalize_unmount(str(mp), "mymount")
        assert not mp.exists()
        assert "mymount" not in _load_registry()

    def test_finalize_unmount_handles_missing_dir(self, monkeypatch, tmp_path):
        from rclone_manager.mount import _finalize_unmount, _save_registry, _load_registry

        monkeypatch.setenv("MOUNT_DIR", str(tmp_path))
        _save_registry({"gone": {"rc_port": 5572}})
        _finalize_unmount(str(tmp_path / "nonexistent"), "gone")
        assert "gone" not in _load_registry()

    def test_fusermount_cmd_prefers_fusermount3(self, monkeypatch):
        from rclone_manager.mount import _fusermount_cmd

        monkeypatch.setattr("shutil.which", lambda *a: "/usr/bin/fusermount3")
        assert _fusermount_cmd() == "fusermount3"

    def test_fusermount_cmd_falls_back_to_fusermount(self, monkeypatch):
        from rclone_manager.mount import _fusermount_cmd

        def fake_which(cmd):
            if cmd == "fusermount":
                return "/usr/bin/fusermount"
            return None

        monkeypatch.setattr("shutil.which", fake_which)
        assert _fusermount_cmd() == "fusermount"

    def test_is_mount_active_true_when_ismount(self, monkeypatch):
        from rclone_manager.mount import _is_mount_active

        monkeypatch.setattr(os.path, "ismount", lambda p: True)
        assert _is_mount_active("/some/mount") is True

    def test_is_mount_active_false(self, monkeypatch):
        from rclone_manager.mount import _is_mount_active

        monkeypatch.setattr(os.path, "ismount", lambda p: False)
        assert _is_mount_active("/some/mount") is False

    def test_unmount_via_rc_success(self, monkeypatch, fake_runner):
        from rclone_manager import mount

        monkeypatch.setattr(mount, "_runner", fake_runner)
        fake_runner.add_response(CommandResult(0))
        assert mount._unmount_via_rc(5572, "/mnt/test") is True

    def test_unmount_via_rc_failure(self, fake_runner):
        from rclone_manager.mount import _unmount_via_rc

        fake_runner.add_response(CommandResult(1, stderr="error"))
        assert _unmount_via_rc(5572, "/mnt/test") is False

    def test_unmount_via_rc_exception(self, fake_runner):
        from rclone_manager.mount import _unmount_via_rc

        fake_runner.add_response(Exception("connection failed"))
        assert _unmount_via_rc(5572, "/mnt/test") is False

    def test_check_pending_uploads_returns_ok_when_no_stats(self, fake_runner, test_output):
        from rclone_manager.mount import _check_pending_uploads
        from rclone_manager import mount

        test_output.add_input_response("")
        monkeypatch = __import__("pytest").MonkeyPatch()
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        fake_runner.add_response(CommandResult(1, stdout=""))

        result = _check_pending_uploads(5572, "test")
        assert result == "ok"
        monkeypatch.undo()


class TestMountRemote:
    def test_checks_fuse_available(self, monkeypatch, test_output, fake_runner):
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

    def test_skips_unsupported_remote_type(self, monkeypatch, test_output, fake_runner, tmp_path):
        from rclone_manager import mount

        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "shutil", type("s", (), {"which": lambda *a: "/usr/bin/fusermount"})())
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        monkeypatch.setattr(mount, "list_rclone_remotes", lambda: ["gphotos"])
        monkeypatch.setattr(mount, "get_remote_type", lambda *a: "google-photos")
        monkeypatch.setattr(mount, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr("rclone_manager.mount.choose_from_list", lambda *a, **kw: ["gphotos"])

        mount.mount_remote()
        assert any("not supported" in m for m in test_output.messages)

    def test_already_mounted_skips(self, monkeypatch, test_output, fake_runner, tmp_path):
        from rclone_manager import mount

        mp = tmp_path / "myremote"
        mp.mkdir()
        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "shutil", type("s", (), {"which": lambda *a: "/usr/bin/fusermount"})())
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        monkeypatch.setattr(mount, "list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(mount, "get_remote_type", lambda *a: "drive")
        monkeypatch.setattr(mount, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr(mount, "get_rclone_flags", lambda *a: [])
        monkeypatch.setattr("rclone_manager.mount.choose_from_list", lambda *a, **kw: ["myremote"])
        monkeypatch.setattr(os.path, "ismount", lambda p: p == str(mp))

        mount.mount_remote()
        assert any("already mounted" in m for m in test_output.messages)

    def test_mount_success(self, monkeypatch, test_output, fake_runner, tmp_path):
        from rclone_manager import mount

        monkeypatch.setenv("MOUNT_DIR", str(tmp_path))
        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "shutil", type("s", (), {"which": lambda *a: "/usr/bin/fusermount"})())
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        monkeypatch.setattr(mount, "list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(mount, "get_remote_type", lambda *a: "drive")
        monkeypatch.setattr(mount, "get_rclone_flags", lambda *a: [])
        monkeypatch.setattr("rclone_manager.mount.choose_from_list", lambda *a, **kw: ["myremote"])
        monkeypatch.setattr(mount, "_find_free_port", lambda *a: 5572)
        monkeypatch.setattr("time.sleep", lambda s: None)
        call_count = [0]

        def mock_is_mount_active(mount_point, proc=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return False
            return True

        monkeypatch.setattr(mount, "_is_mount_active", mock_is_mount_active)

        fake_runner.add_response(CommandResult(0))

        mount.mount_remote()
        assert any("Mounted" in m for m in test_output.messages)

    def test_mount_failure(self, monkeypatch, test_output, fake_runner, tmp_path):
        from rclone_manager import mount

        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "shutil", type("s", (), {"which": lambda *a: "/usr/bin/fusermount"})())
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        monkeypatch.setattr(mount, "list_rclone_remotes", lambda: ["myremote"])
        monkeypatch.setattr(mount, "get_remote_type", lambda *a: "drive")
        monkeypatch.setattr(mount, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr(mount, "get_rclone_flags", lambda *a: [])
        monkeypatch.setattr("rclone_manager.mount.choose_from_list", lambda *a, **kw: ["myremote"])
        monkeypatch.setattr(mount, "_find_free_port", lambda *a: 5572)
        monkeypatch.setattr("time.sleep", lambda s: None)
        monkeypatch.setattr(os.path, "ismount", lambda p: False)

        fake_runner.add_response(CommandResult(1))

        mount.mount_remote()
        assert any("Failed to mount" in m for m in test_output.messages)


class TestUnmountRemote:
    def test_no_mounts_dir(self, monkeypatch, test_output, fake_runner):
        from rclone_manager import mount

        monkeypatch.setattr(mount, "_get_mount_base", lambda: "/nonexistent_mount_base")
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)

        mount.unmount_remote()
        assert any("No mounts directory" in m for m in test_output.messages)

    def test_no_active_mounts(self, monkeypatch, test_output, fake_runner, tmp_path):
        from rclone_manager import mount

        monkeypatch.setattr(mount, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)

        mount.unmount_remote()
        assert any("No mounts to unmount" in m for m in test_output.messages)

    def test_unmount_via_rc_success(self, monkeypatch, tmp_path, test_output, fake_runner):
        from rclone_manager import mount

        mp = tmp_path / "testremote"
        mp.mkdir()
        registry_file = tmp_path / ".rc_ports.json"
        registry_file.write_text('{"testremote": {"rc_port": 5572, "pid": 999}}')

        monkeypatch.setattr(mount, "_get_mount_base", lambda: str(tmp_path))
        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        monkeypatch.setattr(mount, "_fusermount_cmd", lambda: "fusermount")
        monkeypatch.setattr(os.path, "ismount", lambda p: p == str(mp))
        monkeypatch.setattr(os, "listdir", lambda p: ["testremote"])
        monkeypatch.setattr("rclone_manager.mount.choose_from_list", lambda *a, **kw: "All")

        fake_runner.add_response(CommandResult(0, stdout="{}"))
        fake_runner.add_response(CommandResult(0))

        mount.unmount_remote()
        assert any("Unmounted" in m for m in test_output.messages)

    def test_unmount_cancels_when_pending(self, monkeypatch, tmp_path, test_output, fake_runner):
        from rclone_manager import mount

        mp = tmp_path / "testremote"
        mp.mkdir()
        registry_file = tmp_path / ".rc_ports.json"
        registry_file.write_text('{"testremote": {"rc_port": 5572, "pid": 999}}')

        monkeypatch.setenv("MOUNT_DIR", str(tmp_path))
        monkeypatch.setattr(mount, "_is_windows", lambda: False)
        monkeypatch.setattr(mount, "_runner", fake_runner)
        monkeypatch.setattr(mount, "console", test_output)
        monkeypatch.setattr(mount, "_check_pending_uploads", lambda *a, **kw: "cancel")
        monkeypatch.setattr(os.path, "ismount", lambda p: p == str(mp))
        monkeypatch.setattr(os, "listdir", lambda p: ["testremote"])
        monkeypatch.setattr("rclone_manager.mount.choose_from_list", lambda *a, **kw: "All")

        mount.unmount_remote()
        assert any("Skipped" in m for m in test_output.messages)

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
