from unittest.mock import patch

from rclone_manager.ports import RichOutput


class TestRichOutput:
    def test_input_passes_choices_and_default_to_prompt(self):
        out = RichOutput()
        with patch("rich.prompt.Prompt.ask", return_value="y") as ask:
            result = out.input(
                "Serve shared drive as well? (y/n)",
                choices=["y", "n"],
                default="y",
            )
        assert result == "y"
        assert ask.call_args[1]["choices"] == ["y", "n"]
        assert ask.call_args[1]["default"] == "y"

    def test_input_without_choices_still_works(self):
        out = RichOutput()
        with patch("rich.prompt.Prompt.ask", return_value="some input") as ask:
            result = out.input("Enter name")
        assert result == "some input"
        assert ask.call_args[0] == ("Enter name",)
        assert ask.call_args[1]["default"] == ""
