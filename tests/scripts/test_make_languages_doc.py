"""The generated language docs stay in sync with the registry.

``scripts/make_languages_doc.py`` derives both docs/languages.md and the
README's Implemented Languages section from the registry, so neither is
hand-maintained.  These tests pin that contract: running the generator must
leave both committed files unchanged.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "make_languages_doc.py"
README = REPO_ROOT / "README.md"
LANGUAGES_DOC = REPO_ROOT / "docs" / "languages.md"

_README_START = "<!-- IMPLEMENTED:START -->"
_README_END = "<!-- IMPLEMENTED:END -->"
_COMPILERS_START = "<!-- COMPILERS:START -->"
_COMPILERS_END = "<!-- COMPILERS:END -->"
_EXTRA_START = "<!-- EXTRA:START -->"
_EXTRA_END = "<!-- EXTRA:END -->"
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
        "Collatz Multiverse",
        "Container",
        "CV(N)(C)",
        "Decleq",
        "Forbin",
        "Forþ",
        "Home Row",
        "Jaune",
        "MyScript",
        "RAM0",
        "S*bleq",
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


def test_readme_examples_section_is_in_sync() -> None:
    """Regenerating the Examples paragraph leaves it unchanged."""
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
    assert text[start:end] == expected


def test_readme_boolean_count_section_is_in_sync() -> None:
    """Regenerating the boolean-generator count leaves it unchanged."""
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
    assert text[start:end] == expected


def test_readme_counts_match_the_registry() -> None:
    """The rendered counts are the registry's, not a hand-typed number.

    The counts drifted while they sat as prose (46/58/63 against an actual
    47/64/64), which is what moving them inside the markers fixes.  Assert the
    rendered text carries the registry's figures so a wrong-but-in-sync
    number cannot pass the sync tests above.
    """
    module = load_script()
    text_generators = sum(
        1 for lang in module.LANGUAGES.values() if lang.text is not None
    )
    examples = module.render_examples_section()
    assert f"each of the {text_generators}\nlanguages with a text" in examples
    assert f"each of the {len(module.BOOLEAN)} languages" in examples
    assert f"  {len(module.BOOLEAN)} of the" in module.render_boolean_count_section()


def test_boolean_set_names_are_registered() -> None:
    """Every language marked boolean in the matrix is a registered language."""
    module = load_script()
    assert set(module.LANGUAGES) >= module.BOOLEAN


def test_languages_doc_is_in_sync() -> None:
    """Regenerating the capability matrix leaves it unchanged."""
    module = load_script()
    assert LANGUAGES_DOC.read_text() == module.render()
