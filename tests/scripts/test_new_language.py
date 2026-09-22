"""Tests for the new-language scaffolder."""

from pathlib import Path

import pytest

from scripts import new_language


def test_scaffold_creates_source_and_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "src/esolangs/interpreters/_template.py"
    template.parent.mkdir(parents=True)
    template.write_text('"""Template for a new esolang interpreter.\n"""\n')
    monkeypatch.setattr(new_language, "ROOT", tmp_path)
    source, test = new_language.scaffold("Tiny Lang", "other")
    assert source.name == "tiny_lang.py"
    assert test.name == "test_tiny_lang.py"
    assert "Interpreter for Tiny Lang." in source.read_text()


def test_scaffold_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "src/esolangs/interpreters/_template.py"
    template.parent.mkdir(parents=True)
    template.write_text("template")
    target = tmp_path / "src/esolangs/interpreters/other/tiny.py"
    target.parent.mkdir(parents=True)
    target.write_text("owned")
    monkeypatch.setattr(new_language, "ROOT", tmp_path)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Tiny", "other")


def test_a_python_keyword_is_refused() -> None:
    """``class`` scaffolded ``from esolangs.interpreters.other.class import``."""
    with pytest.raises(ValueError, match="keyword"):
        new_language._slug("class")  # noqa: SLF001
