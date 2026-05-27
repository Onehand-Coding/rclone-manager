import pytest
from rclone_manager.ports import FakeCommandRunner, TestOutput


@pytest.fixture
def fake_runner() -> FakeCommandRunner:
    return FakeCommandRunner()


@pytest.fixture
def test_output() -> TestOutput:
    return TestOutput()
