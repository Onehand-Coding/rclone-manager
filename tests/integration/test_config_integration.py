import subprocess
import pytest


pytestmark = pytest.mark.integration


class TestRcloneAvailable:
    def test_rclone_installed(self):
        """Verify rclone binary is available and responds."""
        result = subprocess.run(
            ["rclone", "version"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "rclone" in result.stdout


class TestRcloneLocalRemote:
    def test_list_files_on_local_remote(self, sandbox_rclone_config):
        """List files on a local remote using a temporary config."""
        config_path, remote_dir = sandbox_rclone_config
        result = subprocess.run(
            ["rclone", "lsf", "test-local:", f"--config={config_path}"],
            capture_output=True, text=True, timeout=10,
            cwd=remote_dir,
        )
        assert result.returncode == 0
        assert "file1.txt" in result.stdout

    def test_list_subdirectory(self, sandbox_rclone_config):
        """List files in a subdirectory on local remote."""
        config_path, remote_dir = sandbox_rclone_config
        result = subprocess.run(
            ["rclone", "lsf", "test-local:subdir", f"--config={config_path}"],
            capture_output=True, text=True, timeout=10,
            cwd=remote_dir,
        )
        assert result.returncode == 0
        assert "file2.txt" in result.stdout

    def test_copy_file_via_rclone(self, sandbox_rclone_config):
        """Copy a file from the local remote to a temp dir."""
        config_path, remote_dir = sandbox_rclone_config
        import tempfile
        dest = tempfile.mkdtemp()
        result = subprocess.run(
            [
                "rclone", "copy", "test-local:file1.txt", dest,
                f"--config={config_path}",
            ],
            capture_output=True, text=True, timeout=10,
            cwd=remote_dir,
        )
        assert result.returncode == 0
        assert "hello" in open(f"{dest}/file1.txt").read()
