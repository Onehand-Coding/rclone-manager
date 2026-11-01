import os
import subprocess

from rclone_manager.ports import TestOutput as _TestOutput

import rclone_manager.navigation as nav


def _wire_console(monkeypatch, test_output):
    monkeypatch.setattr(nav, "console", test_output)


def _use_fzf(monkeypatch, results):
    queue = list(results)
    monkeypatch.setattr(nav, "_fzf_available", lambda: True)
    monkeypatch.setattr(nav, "_run_fzf", lambda *a, **kw: queue.pop(0))


def _no_fzf(monkeypatch):
    monkeypatch.setattr(nav, "_fzf_available", lambda: False)


class _StubRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.commands = []

    def check_output(self, command):
        self.commands.append(command)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


class TestChooseFromList:
    def test_empty_items_reports_and_returns_none(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)

        assert nav.choose_from_list([], "Pick") is None
        assert any("No items found" in m for m in test_output.messages)

    def test_fzf_single_selection_returns_string(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _use_fzf(monkeypatch, [["b"]])

        assert nav.choose_from_list(["a", "b"], "Pick") == "b"

    def test_fzf_multi_selection_returns_list(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _use_fzf(monkeypatch, [["a", "b"]])

        assert nav.choose_from_list(["a", "b"], "Pick", multi=True) == ["a", "b"]

    def test_fzf_cancel_returns_none(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _use_fzf(monkeypatch, [[]])

        assert nav.choose_from_list(["a"], "Pick") is None
        assert any("Cancelled" in m for m in test_output.messages)

    def test_quit_returns_none(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        test_output.add_input_response("q")

        assert nav.choose_from_list(["a"], "Pick") is None

    def test_empty_input_reprompts(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        test_output.add_input_response("")
        test_output.add_input_response("1")

        assert nav.choose_from_list(["a"], "Pick") == "a"
        assert any("Please enter a number" in m for m in test_output.messages)

    def test_non_numeric_input_reprompts(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        test_output.add_input_response("x")
        test_output.add_input_response("2")

        assert nav.choose_from_list(["a", "b"], "Pick") == "b"
        assert any("numbers only" in m for m in test_output.messages)

    def test_out_of_range_reprompts(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        test_output.add_input_response("0")
        test_output.add_input_response("1")

        assert nav.choose_from_list(["a"], "Pick") == "a"
        assert any("between 1 and 1" in m for m in test_output.messages)

    def test_comma_selection_returns_list(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        test_output.add_input_response("1,3")

        assert nav.choose_from_list(["a", "b", "c"], "Pick") == ["a", "c"]

    def test_displays_directories_with_trailing_slash(self, monkeypatch, test_output):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        test_output.add_input_response("1")

        nav.choose_from_list(["folder/"], "Pick")

        assert any("folder/" in m for m in test_output.messages)


class TestNavigateLocalFileSystem:
    def _make_tree(self, tmp_path, monkeypatch):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub2").mkdir()
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / ".hidden").write_text("x")
        monkeypatch.setattr(nav.os.path, "expanduser", lambda path: str(tmp_path))
        return tmp_path

    def test_select_current_directory(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        root = self._make_tree(tmp_path, monkeypatch)
        test_output.add_input_response(".")

        assert nav.navigate_local_file_system() == str(root)

    def test_select_file_by_number(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        root = self._make_tree(tmp_path, monkeypatch)
        test_output.add_input_response("3")

        assert nav.navigate_local_file_system() == str(root / "a.txt")

    def test_multi_select_returns_paths(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        root = self._make_tree(tmp_path, monkeypatch)
        test_output.add_input_response("2,3")

        assert nav.navigate_local_file_system() == [str(root / "sub2"), str(root / "a.txt")]

    def test_navigate_into_directory_then_select(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        root = self._make_tree(tmp_path, monkeypatch)
        test_output.add_input_response("1")
        test_output.add_input_response(".")

        assert nav.navigate_local_file_system() == str(root / "sub")

    def test_go_up(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        root = self._make_tree(tmp_path, monkeypatch)
        test_output.add_input_response("..")
        test_output.add_input_response(".")

        assert nav.navigate_local_file_system() == os.path.dirname(str(root))

    def test_quit_returns_none(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        self._make_tree(tmp_path, monkeypatch)
        test_output.add_input_response("q")

        assert nav.navigate_local_file_system() is None

    def test_invalid_choice_reprompts(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        self._make_tree(tmp_path, monkeypatch)
        test_output.add_input_response("abc")
        test_output.add_input_response(".")

        nav.navigate_local_file_system()

        assert any("Invalid choice" in m for m in test_output.messages)

    def test_out_of_range_reprompts(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        self._make_tree(tmp_path, monkeypatch)
        test_output.add_input_response("99")
        test_output.add_input_response(".")

        nav.navigate_local_file_system()

        assert any("Invalid choice" in m for m in test_output.messages)

    def test_missing_directory_resets_home(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        _no_fzf(monkeypatch)
        root = self._make_tree(tmp_path, monkeypatch)
        calls = {"count": 0}

        def fake_listdir(path):
            calls["count"] += 1
            if calls["count"] == 1:
                raise FileNotFoundError(path)
            return []

        monkeypatch.setattr(nav.os, "listdir", fake_listdir)
        test_output.add_input_response(".")

        assert nav.navigate_local_file_system() == str(root)
        assert any("Directory not found" in m for m in test_output.messages)

    def test_fzf_cancel_returns_none(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        self._make_tree(tmp_path, monkeypatch)
        _use_fzf(monkeypatch, [[]])

        assert nav.navigate_local_file_system() is None

    def test_fzf_select_current_directory(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        root = self._make_tree(tmp_path, monkeypatch)
        _use_fzf(monkeypatch, [[". (select this directory)"]])

        assert nav.navigate_local_file_system() == str(root)

    def test_fzf_select_file(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        root = self._make_tree(tmp_path, monkeypatch)
        _use_fzf(monkeypatch, [["📄 a.txt"]])

        assert nav.navigate_local_file_system() == str(root / "a.txt")

    def test_fzf_navigate_into_directory(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        root = self._make_tree(tmp_path, monkeypatch)
        _use_fzf(
            monkeypatch,
            [["📁 sub/"], [". (select this directory)"]],
        )

        assert nav.navigate_local_file_system() == str(root / "sub")

    def test_fzf_go_up(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        root = self._make_tree(tmp_path, monkeypatch)
        _use_fzf(monkeypatch, [[".. (go up)"], [". (select this directory)"]])

        assert nav.navigate_local_file_system() == os.path.dirname(str(root))

    def test_fzf_multi_select_mixed(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        root = self._make_tree(tmp_path, monkeypatch)
        _use_fzf(monkeypatch, [["📄 a.txt", "📁 sub/"]])

        assert nav.navigate_local_file_system() == [str(root / "a.txt"), str(root / "sub")]

    def test_fzf_multi_select_directories(self, monkeypatch, test_output, tmp_path):
        _wire_console(monkeypatch, test_output)
        root = self._make_tree(tmp_path, monkeypatch)
        _use_fzf(monkeypatch, [["📁 sub/", "📁 sub2/"]])

        assert nav.navigate_local_file_system() == [str(root / "sub"), str(root / "sub2")]

    def test_fzf_multi_select_single_directory_navigates(
        self, monkeypatch, test_output, tmp_path
    ):
        _wire_console(monkeypatch, test_output)
        root = self._make_tree(tmp_path, monkeypatch)
        _use_fzf(
            monkeypatch,
            [["📁 sub/"], [". (select this directory)"]],
        )

        assert nav.navigate_local_file_system() == str(root / "sub")


class TestNavigateRemoteFileSystem:
    def _wire(self, monkeypatch, test_output, outputs):
        _wire_console(monkeypatch, test_output)
        runner = _StubRunner(outputs)
        monkeypatch.setattr(nav, "_runner", runner)
        return runner

    def test_select_file_by_number(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        self._wire(monkeypatch, test_output, ["dir/\na.txt\n"])
        test_output.add_input_response("1")

        assert nav.navigate_remote_file_system("remote") == "remote:a.txt"

    def test_navigate_directory_then_select(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        self._wire(monkeypatch, test_output, ["dir/\na.txt\n", "inner.txt\n"])
        test_output.add_input_response("2")
        test_output.add_input_response(".")

        assert nav.navigate_remote_file_system("remote") == "remote:/dir/"

    def test_select_current_remote_path(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        self._wire(monkeypatch, test_output, ["a.txt\n"])
        test_output.add_input_response(".")

        assert nav.navigate_remote_file_system("remote") == "remote:"

    def test_quit_returns_none(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        self._wire(monkeypatch, test_output, ["a.txt\n"])
        test_output.add_input_response("q")

        assert nav.navigate_remote_file_system("remote") is None

    def test_go_up_at_root_reprompts(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        self._wire(monkeypatch, test_output, ["a.txt\n", "a.txt\n"])
        test_output.add_input_response("..")
        test_output.add_input_response(".")

        assert nav.navigate_remote_file_system("remote") == "remote:"

    def test_empty_listing(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        self._wire(monkeypatch, test_output, [""])
        test_output.add_input_response(".")

        nav.navigate_remote_file_system("remote")

        assert any("-- Empty --" in m for m in test_output.messages)

    def test_invalid_choice_reprompts(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        self._wire(monkeypatch, test_output, ["a.txt\n", "a.txt\n"])
        test_output.add_input_response("x")
        test_output.add_input_response(".")

        nav.navigate_remote_file_system("remote")

        assert any("Invalid choice" in m for m in test_output.messages)

    def test_out_of_range_reprompts(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        self._wire(monkeypatch, test_output, ["a.txt\n", "a.txt\n"])
        test_output.add_input_response("9")
        test_output.add_input_response(".")

        nav.navigate_remote_file_system("remote")

        assert any("Invalid choice" in m for m in test_output.messages)

    def test_rclone_failure_returns_current_path(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        runner = _StubRunner([subprocess.CalledProcessError(1, "rclone")])
        monkeypatch.setattr(nav, "_runner", runner)
        _wire_console(monkeypatch, test_output)

        assert nav.navigate_remote_file_system("remote") == "remote:"
        assert any("Error listing remote directory" in m for m in test_output.messages)

    def test_fzf_cancel_returns_none(self, monkeypatch, test_output):
        self._wire(monkeypatch, test_output, ["a.txt\n"])
        _use_fzf(monkeypatch, [[]])

        assert nav.navigate_remote_file_system("remote") is None

    def test_fzf_select_file(self, monkeypatch, test_output):
        self._wire(monkeypatch, test_output, ["a.txt\n"])
        _use_fzf(monkeypatch, [["📄 a.txt"]])

        assert nav.navigate_remote_file_system("remote") == "remote:/a.txt"

    def test_fzf_select_current_path(self, monkeypatch, test_output):
        self._wire(monkeypatch, test_output, ["a.txt\n"])
        _use_fzf(monkeypatch, [[". (select this path)"]])

        assert nav.navigate_remote_file_system("remote") == "remote:"

    def test_fzf_navigate_into_directory(self, monkeypatch, test_output):
        self._wire(monkeypatch, test_output, ["dir/\n", "inner.txt\n"])
        _use_fzf(
            monkeypatch,
            [["📁 dir/"], [". (select this path)"]],
        )

        assert nav.navigate_remote_file_system("remote") == "remote:/dir/"

    def test_fzf_go_up_at_root_reprompts(self, monkeypatch, test_output):
        self._wire(monkeypatch, test_output, ["a.txt\n", "a.txt\n"])
        _use_fzf(
            monkeypatch,
            [[".. (go up)"], [". (select this path)"]],
        )

        assert nav.navigate_remote_file_system("remote") == "remote:"

    def test_fzf_go_up_from_child(self, monkeypatch, test_output):
        self._wire(monkeypatch, test_output, ["dir/\n", "inner.txt\n", "dir/\n"])
        _use_fzf(
            monkeypatch,
            [["📁 dir/"], [".. (go up)"], [". (select this path)"]],
        )

        assert nav.navigate_remote_file_system("remote") == "remote:/"

    def test_fzf_multi_select_mixed(self, monkeypatch, test_output):
        self._wire(monkeypatch, test_output, ["dir/\na.txt\n"])
        _use_fzf(monkeypatch, [["📄 a.txt", "📁 dir/"]])

        assert nav.navigate_remote_file_system("remote") == [
            "remote:/a.txt",
            "remote:/dir/",
        ]

    def test_fzf_multi_select_directories(self, monkeypatch, test_output):
        self._wire(monkeypatch, test_output, ["a/\nb/\n"])
        _use_fzf(monkeypatch, [["📁 a/", "📁 b/"]])

        assert nav.navigate_remote_file_system("remote") == [
            "remote:/a/",
            "remote:/b/",
        ]


class _PromptRecordingOutput(_TestOutput):
    def __init__(self):
        super().__init__()
        self.prompts = []

    def input(self, prompt="", **kwargs):
        self.prompts.append(prompt)
        return super().input(prompt, **kwargs)


class TestPurposePrompts:
    def test_local_prompt_mentions_purpose(self, monkeypatch, tmp_path):
        output = _PromptRecordingOutput()
        monkeypatch.setattr(nav, "console", output)
        _no_fzf(monkeypatch)
        (tmp_path / "a.txt").write_text("x")
        monkeypatch.setattr(nav.os.path, "expanduser", lambda path: str(tmp_path))
        output.add_input_response(".")

        nav.navigate_local_file_system(purpose="source directory")

        assert any("source directory" in prompt for prompt in output.prompts)

    def test_remote_prompt_mentions_purpose(self, monkeypatch):
        output = _PromptRecordingOutput()
        monkeypatch.setattr(nav, "console", output)
        _no_fzf(monkeypatch)
        monkeypatch.setattr(nav, "_runner", _StubRunner(["a.txt\n"]))
        output.add_input_response(".")

        nav.navigate_remote_file_system("remote", purpose="destination path")

        assert any("destination path" in prompt for prompt in output.prompts)


class TestRemoteGoUpFromChild:
    def test_numbered_mode_goes_up_one_level(self, monkeypatch, test_output):
        _no_fzf(monkeypatch)
        _wire_console(monkeypatch, test_output)
        monkeypatch.setattr(nav, "_runner", _StubRunner(["a.txt\ndir/\n", "", ""]))
        test_output.add_input_response("2")
        test_output.add_input_response("..")
        test_output.add_input_response(".")

        assert nav.navigate_remote_file_system("remote") == "remote:/"
