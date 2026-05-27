import pytest


class TestArgParse:
    def _run_parse(self, args):
        """Helper to run argparse with given args and return parsed namespace."""
        from rclone_manager.cli import main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager"] + args
            main()
        finally:
            sys.argv = old_argv

    def test_generate_config_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "generate_default_config", lambda: called.append(True))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "generate-config"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert len(called) == 1

    def test_serve_remote_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "serve_remote", lambda: called.append(True))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "serve-remote"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert len(called) == 1

    def test_upload_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "upload_backup", lambda overwrite=False: called.append(("upload", overwrite)))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "upload", "--overwrite"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert len(called) == 1
        assert called[0] == ("upload", True)

    def test_download_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "download_backup", lambda overwrite=False: called.append(("download", overwrite)))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "download"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert len(called) == 1
        assert called[0] == ("download", False)

    def test_sync_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(
            cli, "sync_remotes",
            lambda dry_run=False, preview=False, force=False: called.append(("sync", dry_run, preview, force)),
        )
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "sync", "--dry-run", "--preview"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert len(called) == 1
        assert called[0] == ("sync", True, True, False)

    def test_mount_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "mount_remote", lambda: called.append(True))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "mount"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert len(called) == 1

    def test_unmount_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "unmount_remote", lambda: called.append(True))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "unmount"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert len(called) == 1

    def test_status_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "show_status", lambda: called.append(True))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "status"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert len(called) == 1

    def test_sync_pairs_add(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "sync_pairs_add", lambda: called.append("add"))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "sync-pairs", "add"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert called == ["add"]

    def test_sync_pairs_list(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(cli, "sync_pairs_list", lambda: called.append("list"))
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "sync-pairs", "list"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert called == ["list"]

    def test_sync_pairs_run_with_dry_run(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(
            cli, "sync_pairs_run",
            lambda dry_run=False: called.append(("run", dry_run)),
        )
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "sync-pairs", "run", "--dry-run"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert called == [("run", True)]

    def test_fzf_command(self, monkeypatch):
        from rclone_manager import cli

        called = []
        monkeypatch.setattr(
            "rclone_manager.utils._toggle_fzf",
            lambda action: called.append(action),
        )
        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "fzf", "on"]
            cli.main()
        finally:
            sys.argv = old_argv

        assert called == ["on"]

    def test_unknown_command_prints_help(self, monkeypatch, capsys):
        from rclone_manager import cli

        monkeypatch.setattr(cli, "get_project_root", lambda: "/tmp")
        monkeypatch.setattr(cli, "setup_env", lambda root: None)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["rclone-manager", "unknown-cmd"]
            with pytest.raises(SystemExit):
                cli.main()
        finally:
            sys.argv = old_argv

        captured = capsys.readouterr()
        assert "usage:" in captured.err or "usage:" in captured.out
