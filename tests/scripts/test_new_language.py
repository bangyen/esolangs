"""Tests for the new-language scaffolder."""

from pathlib import Path

import pytest

from scripts import new_language


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    template = tmp_path / "src/esolangs/interpreters/_template.py"
    template.parent.mkdir(parents=True)
    template.write_text('"""Template for a new esolang interpreter.\n"""\n')
    monkeypatch.setattr(new_language, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.usefixtures("root")
def test_scaffold_creates_source_generator_and_tests() -> None:
    source, test, generator, generator_test = new_language.scaffold(
        "Tiny Lang", "other"
    )
    assert source.name == generator.name == "tiny_lang.py"
    assert (test.name, generator_test.name) == (
        "test_tiny_lang.py",
        "test_boolean_tiny_lang.py",
    )
    assert "Interpreter for Tiny Lang." in source.read_text()
    assert "def tiny_lang(truth_table: str) -> str:" in generator.read_text()


@pytest.mark.usefixtures("root")
def test_an_interpreter_only_language_gets_no_generator() -> None:
    paths = new_language.scaffold("Tiny", "other", generator=False)
    assert [path.name for path in paths] == ["tiny.py", "test_tiny.py"]


def test_scaffold_refuses_overwrite(root: Path) -> None:
    target = root / "src/esolangs/interpreters/other/tiny.py"
    target.parent.mkdir(parents=True)
    target.write_text("owned")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        new_language.scaffold("Tiny", "other")


@pytest.mark.parametrize(
    ("name", "slug"), [("123", "one_two_three"), ("Piet++", "piet_plus_plus")]
)
def test_the_slug_is_the_registry_id(name: str, slug: str) -> None:
    """A second slug rule refused ``123`` and gave Piet++ Piet's file."""
    assert new_language._slug(name) == slug  # noqa: SLF001
    with pytest.raises(ValueError, match="keyword"):
        new_language._slug("class")  # noqa: SLF001


def test_remove_cuts_only_entries_that_own_their_lines(tmp_path: Path) -> None:
    path = tmp_path / "table.py"
    path.write_text(
        "from esolangs.tools.gone import gone\n"
        "from esolangs.tools.gone import PAIR\n"
        'T = {\n    "gone": 1,\n    "kept": PAIR,\n}\n'
        'L = ["gone", "kept"]\n'
        'run_gone = _runner("gone")\n'
    )
    modules = {"esolangs.tools.gone"}
    assert new_language._drop_entries(path, {"gone"}, modules) == 3  # noqa: SLF001
    # The import another entry still uses stays.
    assert path.read_text() == (
        "from esolangs.tools.gone import PAIR\n"
        'T = {\n    "kept": PAIR,\n}\nL = ["gone", "kept"]\n'
    )
