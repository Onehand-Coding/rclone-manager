from __future__ import annotations

import subprocess
from typing import Any, ContextManager, List, Protocol


class CommandResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class OutputPort(Protocol):
    def print(self, *values: Any, style: str = "") -> None: ...

    def status(self, message: str = "") -> ContextManager[Any]: ...

    def rule(self, title: str = "") -> None: ...

    def input(self, prompt: str = "") -> str: ...


class CommandRunner(Protocol):
    def run(
        self, command: List[str], **kwargs: Any
    ) -> CommandResult: ...

    def popen(
        self, command: List[str], **kwargs: Any
    ) -> subprocess.Popen: ...

    def check_output(self, command: List[str], **kwargs: Any) -> str: ...


class RichOutput:
    def __init__(self) -> None:
        from rich.console import Console

        self._console = Console()

    def print(self, *values: Any, style: str = "") -> None:
        self._console.print(*values)

    def status(self, message: str = "") -> ContextManager[Any]:
        return self._console.status(message)

    def rule(self, title: str = "") -> None:
        self._console.rule(title)

    def input(self, prompt: str = "") -> str:
        from rich.prompt import Prompt
        return Prompt.ask(prompt)


class RealCommandRunner:
    def run(
        self, command: List[str], **kwargs: Any
    ) -> CommandResult:
        result = subprocess.run(command, **kwargs)
        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout if isinstance(result.stdout, str) else "",
            stderr=result.stderr if isinstance(result.stderr, str) else "",
        )

    def popen(self, command: List[str], **kwargs: Any) -> subprocess.Popen:
        return subprocess.Popen(command, **kwargs)

    def check_output(self, command: List[str], **kwargs: Any) -> str:
        return subprocess.check_output(command, **kwargs).decode("utf-8")


class TestOutput:
    def __init__(self) -> None:
        self.messages: List[str] = []
        self.input_responses: List[str] = []

    def print(self, *values: Any, style: str = "") -> None:
        self.messages.append(" ".join(str(v) for v in values))

    def status(self, message: str = "") -> ContextManager[Any]:
        class FakeStatus:
            def update(self, text: str = "") -> None:
                pass

            def __enter__(self) -> "FakeStatus":
                return self

            def __exit__(self, *args: Any) -> None:
                pass

        return FakeStatus()

    def rule(self, title: str = "") -> None:
        pass

    def add_input_response(self, value: str) -> None:
        self.input_responses.append(value)

    def input(self, prompt: str = "", **kwargs: Any) -> str:
        if self.input_responses:
            return self.input_responses.pop(0)
        raise IndexError("TestOutput.input() called with no input_responses queued")


class FakeCommandRunner:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.commands: List[List[str]] = []
        self.responses: List[CommandResult] = []
        self.kwargs: List[dict] = []

    def add_response(self, result: CommandResult) -> None:
        self.responses.append(result)

    def run(self, command: List[str], **kwargs: Any) -> CommandResult:
        self.commands.append(command)
        self.kwargs.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        raise IndexError("FakeCommandRunner.run() called with no responses queued")

    def popen(self, command: List[str], **kwargs: Any) -> subprocess.Popen:
        self.commands.append(command)
        raise NotImplementedError("FakeCommandRunner.popen not implemented — mock it")

    def check_output(self, command: List[str], **kwargs: Any) -> str:
        self.commands.append(command)
        if self.responses:
            return self.responses.pop(0).stdout
        raise IndexError("FakeCommandRunner.check_output() called with no responses queued")
