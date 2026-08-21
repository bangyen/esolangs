"""The generated language docs stay in sync with the registry.

``scripts/make_languages_doc.py`` derives both docs/languages.md and the
README's Implemented Languages section from the registry, so neither is
hand-maintained.  These tests pin that contract: running the generator must
leave both committed files unchanged.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "make_languages_doc.py"
README = REPO_ROOT / "README.md"
LANGUAGES_DOC = REPO_ROOT / "docs" / "languages.md"

_README_START = "<!-- IMPLEMENTED:START -->"
_README_END = "<!-- IMPLEMENTED:END -->"
_COMPILERS_START = "<!-- COMPILERS:START -->"
_COMPILERS_END = "<!-- COMPILERS:END -->"
_EXTRA_START = "<!-- EXTRA:START -->"
_EXTRA_END = "<!-- EXTRA:END -->"


def load_script() -> object:
    spec = importlib.util.spec_from_file_location("make_languages_doc", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_readme_languages_section_is_in_sync() -> None:
    """Regenerating the README section leaves it unchanged."""
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
    assert text[start:end] == expected


def test_readme_compilers_section_is_in_sync() -> None:
    """Regenerating the compilers section leaves it unchanged."""
    module = load_script()
    text = README.read_text()
    start = text.index(_COMPILERS_START)
    end = text.index(_COMPILERS_END) + len(_COMPILERS_END)
    expected = (
        _COMPILERS_START
        + "\n\n"
        + module.render_compilers_section()
        + "\n\n"
        + _COMPILERS_END
    )
    assert text[start:end] == expected


def test_compiler_sets_match_the_compiler_modules() -> None:
    """The compiler lists are derived from the compiler source files."""
    module = load_script()
    assert {
        "AddSubJump",
        "BF-PDA",
        "BFStack",
        "Home Row",
        "Jaune",
        "RAM0",
        "Suffolk",
        "Unsquare",
    } == module.ASSEMBLY_COMPILERS


def test_readme_extra_section_is_in_sync() -> None:
    """Regenerating the Extra Implementations section leaves it unchanged."""
    module = load_script()
    text = README.read_text()
    start = text.index(_EXTRA_START)
    end = text.index(_EXTRA_END) + len(_EXTRA_END)
    expected = (
        _EXTRA_START + "\n\n" + module.render_extra_section() + "\n\n" + _EXTRA_END
    )
    assert text[start:end] == expected


def test_boolean_set_names_are_registered() -> None:
    """Every language marked boolean in the matrix is a registered language."""
    module = load_script()
    assert set(module.LANGUAGES) >= module.BOOLEAN


def test_languages_doc_is_in_sync() -> None:
    """Regenerating the capability matrix leaves it unchanged."""
    module = load_script()
    assert LANGUAGES_DOC.read_text() == module.render()
