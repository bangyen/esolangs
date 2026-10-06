"""Shared fixtures for the test suite, and readers for its data files."""

from pathlib import Path

_DIR = Path(__file__).parent


def text(name: str) -> str:
    """Return ``tests/fixtures/<name>`` exactly as stored."""
    return (_DIR / name).read_text(encoding="utf-8")


def grid(name: str) -> list[str]:
    """Return a fixture's lines, trailing spaces and blank rows kept."""
    return text(name).splitlines()
