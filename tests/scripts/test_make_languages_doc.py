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
USAGE_DOC = REPO_ROOT / "docs" / "usage.md"

_README_START = "<!-- IMPLEMENTED:START -->"
_README_END = "<!-- IMPLEMENTED:END -->"
_EXAMPLES_START = "<!-- EXAMPLES:START -->"
_EXAMPLES_END = "<!-- EXAMPLES:END -->"
_BOOLEAN_COUNT_START = "<!-- BOOLEAN-COUNT:START -->"
_BOOLEAN_COUNT_END = "<!-- BOOLEAN-COUNT:END -->"
_SHAPES_START = "<!-- INPUT-SHAPES:START -->"
_SHAPES_END = "<!-- INPUT-SHAPES:END -->"
_API_START = "<!-- PUBLIC-API:START -->"
_API_END = "<!-- PUBLIC-API:END -->"


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
    examples = module.render_examples_section()
    assert f"each of the {len(module.BOOLEAN)}\nlanguages with a boolean" in examples
    assert f"  {len(module.BOOLEAN)} of the" in module.render_boolean_count_section()


def _marked(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end) + len(end)]


def test_usage_input_shapes_table_is_in_sync() -> None:
    """Regenerating the stdin table leaves it unchanged.

    The table replaced three hand-written prose copies of the same four
    exceptions, one of which was wrong for two years' worth of commits.
    """
    module = load_script()
    expected = (
        _SHAPES_START
        + "\n\n"
        + module.render_input_shapes_section()
        + "\n\n"
        + _SHAPES_END
    )
    assert _marked(USAGE_DOC.read_text(), _SHAPES_START, _SHAPES_END) == expected


def test_usage_api_list_is_in_sync() -> None:
    """Regenerating the exported-callable list leaves it unchanged."""
    module = load_script()
    expected = _API_START + "\n\n" + module.render_api_section() + "\n\n" + _API_END
    assert _marked(USAGE_DOC.read_text(), _API_START, _API_END) == expected


def test_the_shape_table_carries_the_encoders_output() -> None:
    """A wrong-but-in-sync table cannot pass the sync test above.

    ``_SAMPLE_BITS`` is three bits for a reason: at two, Taglate's padding
    is invisible and Fargo's decimal and binary readings coincide, so a
    two-bit table would render identically for a language whose shape had
    silently changed.
    """
    module = load_script()
    rendered = module.render_input_shapes_section()
    assert "| Fargo | `row_index` | `0`/`1` | `'5\\n'` |" in rendered
    assert "| Taglate | `line_per_bit_padded` | `0`/`1` | `'0\\n1\\n0\\n1\\n'` |" in (
        rendered
    )


def test_boolean_set_names_are_registered() -> None:
    """Every language marked boolean in the matrix is a registered language."""
    module = load_script()
    assert set(module.LANGUAGES) >= module.BOOLEAN


def test_languages_doc_is_in_sync() -> None:
    """Regenerating the capability matrix leaves it unchanged."""
    module = load_script()
    assert LANGUAGES_DOC.read_text() == module.render()
