"""Readers for language-owned test fixtures."""

from pathlib import Path

from tests.support.paths import ROOT


def path(language: str, name: str) -> Path:
    """Return a fixture path under a canonical language ID."""
    root = ROOT / "src/esolangs/languages" / language / "tests"
    direct = root / name
    return direct if direct.is_file() else root / "fixtures" / name


def text(language: str, name: str) -> str:
    """Return a language fixture exactly as stored."""
    return path(language, name).read_text(encoding="utf-8")


def grid(language: str, name: str) -> list[str]:
    """Return fixture lines, retaining trailing spaces and blank rows."""
    return text(language, name).splitlines()
