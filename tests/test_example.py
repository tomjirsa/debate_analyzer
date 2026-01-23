"""Example test file to demonstrate test structure."""

from debate_analyzer import __version__


def test_version() -> None:
    """Test that version is properly set."""
    assert __version__ == "0.1.0"


def test_example() -> None:
    """Example test case."""
    assert True


class TestExample:
    """Example test class."""

    def test_method_example(self) -> None:
        """Example test method."""
        assert 1 + 1 == 2
