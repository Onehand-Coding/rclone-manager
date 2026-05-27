import os
from pathlib import Path
import pytest
from rclone_manager.config import build_filter_args, get_filters


class TestBuildFilterArgs:
    """Tests for build_filter_args() which converts filter dicts to rclone CLI args."""

    def test_excludes_hidden_by_default(self):
        """When INCLUDE_HIDDEN is not set, --exclude .* and --exclude .*/ should be present."""
        result = build_filter_args({"exclude": [], "include": []})
        assert "--exclude" in result
        assert ".*" in result

    def test_hidden_excluded_when_env_false(self, monkeypatch):
        monkeypatch.setenv("INCLUDE_HIDDEN", "false")
        result = build_filter_args({"exclude": [], "include": []})
        assert "--exclude" in result

    def test_hidden_included_when_env_true(self, monkeypatch):
        monkeypatch.setenv("INCLUDE_HIDDEN", "true")
        result = build_filter_args({"exclude": [], "include": []})
        assert "--exclude" not in result

    def test_exclude_patterns_added(self):
        filters = {"exclude": ["*.log", "tmp/"], "include": []}
        result = build_filter_args(filters)
        exclude_idx = [i for i, a in enumerate(result) if a == "--exclude"]
        exclude_vals = [result[i + 1] for i in exclude_idx if i + 1 < len(result)]
        assert "*.log" in exclude_vals
        assert "tmp/" in exclude_vals

    def test_include_patterns_added(self):
        filters = {"exclude": [], "include": ["*.py", "src/"]}
        result = build_filter_args(filters)
        include_idx = [i for i, a in enumerate(result) if a == "--include"]
        include_vals = [result[i + 1] for i in include_idx if i + 1 < len(result)]
        assert "*.py" in include_vals
        assert "src/" in include_vals

    def test_both_exclude_and_include(self):
        """When both present, order should be: hidden exclude, user exclude, user include."""
        filters = {"exclude": ["*.log"], "include": ["*.py"]}
        result = build_filter_args(filters)
        assert result.count("--exclude") >= 2  # hidden + user
        assert result.count("--include") == 1


class TestGetFilters:
    """Tests for get_filters() which reads filter patterns from config.ini."""

    def test_returns_empty_when_config_missing(self, tmp_path):
        """When no configs/config.ini exists, returns empty filters."""
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"exclude": [], "include": []}

    def test_parses_exclude_patterns(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "config.ini"
        config_file.write_text("[filters]\nexclude = *.log\n  tmp/\ninclude = ")
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"exclude": ["*.log", "tmp/"], "include": []}

    def test_parses_include_patterns(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "config.ini"
        config_file.write_text("[filters]\ninclude = *.py\n  src/\nexclude = ")
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"include": ["*.py", "src/"], "exclude": []}

    def test_parses_both_patterns(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "config.ini"
        config_file.write_text("[filters]\nexclude = *.log\ninclude = *.py")
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"exclude": ["*.log"], "include": ["*.py"]}

    def test_missing_filters_section(self, tmp_path):
        """Config exists but has no [filters] section — returns empty."""
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        config_file = config_dir / "config.ini"
        config_file.write_text("[DEFAULT]\nkey = value\n")
        result = get_filters(root_dir=str(tmp_path))
        assert result == {"exclude": [], "include": []}
