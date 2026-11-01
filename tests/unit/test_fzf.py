import os
from configparser import ConfigParser

from rclone_manager.ports import CommandResult


class _StubRunner:
    def __init__(self, result):
        self.result = result
        self.commands = []
        self.kwargs = []

    def run(self, command, **kwargs):
        self.commands.append(command)
        self.kwargs.append(kwargs)
        return self.result


class TestFzfAvailable:
    def test_disabled_by_env(self, monkeypatch):
        from rclone_manager import fzf

        monkeypatch.setenv("USE_FZF", "false")
        monkeypatch.setattr(fzf.shutil, "which", lambda name: "/usr/bin/fzf")

        assert fzf._fzf_available() is False

    def test_false_when_fzf_missing(self, monkeypatch):
        from rclone_manager import fzf

        monkeypatch.delenv("USE_FZF", raising=False)
        monkeypatch.setattr(fzf.shutil, "which", lambda name: None)

        assert fzf._fzf_available() is False

    def test_true_when_enabled_and_installed(self, monkeypatch):
        from rclone_manager import fzf

        monkeypatch.setenv("USE_FZF", "TRUE")
        monkeypatch.setattr(fzf.shutil, "which", lambda name: "/usr/bin/fzf")

        assert fzf._fzf_available() is True


class TestRunFzf:
    def test_builds_prompt_and_multi_flag(self, monkeypatch):
        from rclone_manager import fzf

        runner = _StubRunner(CommandResult(0, "a\nb\n"))
        monkeypatch.setattr(fzf, "_runner", runner)

        result = fzf._run_fzf(["a", "b"], prompt="Pick", multi=True)

        assert result == ["a", "b"]
        assert runner.commands[0][:2] == ["fzf", "--height=40%"]
        assert "--prompt" in runner.commands[0]
        assert runner.commands[0][runner.commands[0].index("--prompt") + 1] == "Pick "
        assert "-m" in runner.commands[0]
        assert runner.kwargs[0]["input"] == "a\nb"

    def test_omits_optional_flags(self, monkeypatch):
        from rclone_manager import fzf

        runner = _StubRunner(CommandResult(0, "a\n"))
        monkeypatch.setattr(fzf, "_runner", runner)

        fzf._run_fzf(["a"])

        assert "--prompt" not in runner.commands[0]
        assert "-m" not in runner.commands[0]

    def test_returns_empty_on_unexpected_returncode(self, monkeypatch):
        from rclone_manager import fzf

        monkeypatch.setattr(fzf, "_runner", _StubRunner(CommandResult(2, "a\n")))

        assert fzf._run_fzf(["a"]) == []

    def test_accepts_returncode_one_and_drops_blank_lines(self, monkeypatch):
        from rclone_manager import fzf

        monkeypatch.setattr(
            fzf, "_runner", _StubRunner(CommandResult(1, "a\n\nb\n"))
        )

        assert fzf._run_fzf(["a", "b"]) == ["a", "b"]

    def test_empty_output_returns_empty_list(self, monkeypatch):
        from rclone_manager import fzf

        monkeypatch.setattr(fzf, "_runner", _StubRunner(CommandResult(0, "")))

        assert fzf._run_fzf(["a"]) == []


class TestToggleFzf:
    def _config_path(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        return config_dir / "config.ini"

    def test_missing_config_file_warns(self, monkeypatch, tmp_path, test_output):
        from rclone_manager import config, fzf

        monkeypatch.setattr(config, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(fzf, "console", test_output)

        fzf._toggle_fzf("on")

        assert any("config.ini not found" in m for m in test_output.messages)
        assert not (tmp_path / "configs" / "config.ini").exists()

    def test_status_reports_config_fzf_and_active(self, monkeypatch, tmp_path, test_output):
        from rclone_manager import config, fzf

        self._config_path(tmp_path).write_text("[DEFAULT]\n")
        monkeypatch.setattr(config, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(fzf, "console", test_output)
        monkeypatch.setattr(fzf.shutil, "which", lambda name: "/usr/bin/fzf")

        fzf._toggle_fzf("status")

        joined = "\n".join(test_output.messages)
        assert "Fuzzy Search Status" in joined
        assert "Config" in joined
        assert "installed" in joined
        assert "Active" in joined

    def test_status_reports_disabled_and_missing(self, monkeypatch, tmp_path, test_output):
        from rclone_manager import config, fzf

        self._config_path(tmp_path).write_text("[DEFAULT]\n")
        monkeypatch.setattr(config, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(fzf, "console", test_output)
        monkeypatch.setenv("USE_FZF", "false")
        monkeypatch.setattr(fzf.shutil, "which", lambda name: None)

        fzf._toggle_fzf("status")

        joined = "\n".join(test_output.messages)
        assert "OFF" in joined
        assert "not found" in joined

    def test_enables_fzf_in_config(self, monkeypatch, tmp_path, test_output):
        from rclone_manager import config, fzf

        config_path = self._config_path(tmp_path)
        config_path.write_text("[DEFAULT]\n")
        monkeypatch.setattr(config, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(fzf, "console", test_output)

        fzf._toggle_fzf("on")

        parser = ConfigParser()
        parser.read(config_path)
        assert parser["DEFAULT"]["USE_FZF"] == "true"
        assert any("set to" in m for m in test_output.messages)

    def test_disables_fzf_in_config(self, monkeypatch, tmp_path, test_output):
        from rclone_manager import config, fzf

        config_path = self._config_path(tmp_path)
        config_path.write_text("[DEFAULT]\nUSE_FZF = true\n")
        monkeypatch.setattr(config, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(fzf, "console", test_output)
        monkeypatch.delenv("USE_FZF", raising=False)

        fzf._toggle_fzf("off")

        parser = ConfigParser()
        parser.read(config_path)
        assert parser["DEFAULT"]["USE_FZF"] == "false"
        assert os.path.exists(config_path)
