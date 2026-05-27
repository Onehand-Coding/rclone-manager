import pytest


@pytest.fixture
def sandbox_rclone_config(tmp_path):
    """Create a temporary rclone config with a local filesystem remote."""
    config_path = tmp_path / "rclone.conf"
    remote_dir = tmp_path / "testdata"
    remote_dir.mkdir()

    (remote_dir / "file1.txt").write_text("hello")
    (remote_dir / "subdir").mkdir()
    (remote_dir / "subdir" / "file2.txt").write_text("world")

    config_path.write_text(f"[test-local]\ntype = local\nroot = {remote_dir}\n")
    return str(config_path), str(remote_dir)
