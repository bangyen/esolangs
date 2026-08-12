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


def test_languages_doc_is_in_sync() -> None:
    """Regenerating the capability matrix leaves it unchanged."""
    module = load_script()
    assert LANGUAGES_DOC.read_text() == module.render()
