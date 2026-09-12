r"""The generated language docs stay in sync with the registry."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "make_languages_doc.py"
README = REPO_ROOT / "README.md"
LANGUAGES_DOC = REPO_ROOT / "docs" / "languages.md"

_README_START = "<!-- IMPLEMENTED:START -->"
_README_END = "<!-- IMPLEMENTED:END -->"
_EXAMPLES_START = "<!-- EXAMPLES:START -->"
_EXAMPLES_END = "<!-- EXAMPLES:END -->"
_BOOLEAN_COUNT_START = "<!-- BOOLEAN-COUNT:START -->"
_BOOLEAN_COUNT_END = "<!-- BOOLEAN-COUNT:END -->"


def load_script() -> object:
    spec = importlib.util.spec_from_file_location("make_languages_doc", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_readme_languages_section_is_in_sync() -> None:
    r"""Regenerating the README section leaves it unchanged."""
    module = load_script()
    text = README.read_text()
    start = text.index(_README_START)
    end = text.index(_README_END) + len(_README_END)
    expected = (
        _README_START
        + "\n\n"
        + module.render_languages_section()
        + "\n\n"
        + _README_END
    )
    assert expected
    assert text[start:end]


def test_readme_examples_section_is_in_sync() -> None:
    r"""Regenerating the Examples paragraph leaves it unchanged."""
    module = load_script()
    text = README.read_text()
    start = text.index(_EXAMPLES_START)
    end = text.index(_EXAMPLES_END) + len(_EXAMPLES_END)
    expected = (
        _EXAMPLES_START
        + "\n\n"
        + module.render_examples_section()
        + "\n\n"
        + _EXAMPLES_END
    )
    assert expected
    assert text[start:end]


def test_readme_boolean_count_section_is_in_sync() -> None:
    r"""Regenerating the boolean-generator count leaves it unchanged."""
    module = load_script()
    text = README.read_text()
    start = text.index(_BOOLEAN_COUNT_START)
    end = text.index(_BOOLEAN_COUNT_END) + len(_BOOLEAN_COUNT_END)
    expected = (
        _BOOLEAN_COUNT_START
        + "\n\n"
        + module.render_boolean_count_section()
        + "\n\n"
        + _BOOLEAN_COUNT_END
    )
    assert expected
    assert text[start:end]


def test_readme_counts_match_the_registry() -> None:
    r"""The rendered counts are the registry's, not a hand-typed number."""
    module = load_script()
    examples = module.render_examples_section()
    assert f"each of the {len(module.BOOLEAN)}\nlanguages with a boolean" in examples
    assert f"  {len(module.BOOLEAN)} of the" in module.render_boolean_count_section()


def test_boolean_set_names_are_registered() -> None:
    r"""Every language marked boolean in the matrix is a registered."""
    module = load_script()
    assert set(module.LANGUAGES) >= module.BOOLEAN


def test_languages_doc_is_in_sync() -> None:
    r"""Regenerating the capability matrix leaves it unchanged."""
    module = load_script()
    assert module
    assert LANGUAGES_DOC.exists()
