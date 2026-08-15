"""Unit tests for the wiki-spec hash verification.

``scripts/verify_wiki_specs.py`` hashes each language's raw wikitext so a
changed spec can be spotted without re-reading every interpreter.  These
tests pin the offline pieces (title mapping, hashing) and that the committed
hash file only covers registered languages.
"""

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_wiki_specs.py"
HASHES = REPO_ROOT / "docs" / "wiki-specs.json"


def load_script() -> object:
    spec = importlib.util.spec_from_file_location("verify_wiki_specs", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_page_title_replaces_spaces() -> None:
    module = load_script()
    assert module.page_title("Home Row") == "Home_Row"
    assert module.page_title("2 Bits, 1 Byte") == "2_Bits,_1_Byte"
    assert module.page_title("S*bleq") == "S*bleq"


def test_hash_is_stable_sha256() -> None:
    module = load_script()
    h = module.page_hash("abc")
    assert len(h) == 64
    assert h == module.page_hash("abc")
    assert h != module.page_hash("abd")


def test_recorded_hashes_are_registered_languages() -> None:
    """Every recorded hash belongs to a language the registry knows."""
    import esolangs.registry

    recorded = json.loads(HASHES.read_text())
    assert set(recorded) <= set(esolangs.registry.LANGUAGES)


def test_recorded_hashes_look_like_sha256() -> None:
    recorded = json.loads(HASHES.read_text())
    for lang, h in recorded.items():
        assert len(h) == 64, lang
        assert all(c in "0123456789abcdef" for c in h), lang
