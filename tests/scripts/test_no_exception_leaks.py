"""Leak sweeps select and fingerprint imported helper dependencies."""

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import verify_no_exception_leaks as leaks


@pytest.fixture
def source_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(leaks, "_ROOT", tmp_path)
    monkeypatch.setattr(leaks, "_SHARED", ())
    files = {
        "scripts/_scope.py": "",
        "src/esolangs/__init__.py": "",
        "src/esolangs/interpreters/__init__.py": "",
        "src/esolangs/interpreters/other/__init__.py": "",
        "src/esolangs/interpreters/other/fixture.py": "from . import helper\n",
        "src/esolangs/interpreters/other/helper.py": "from ..shared import aux\n",
        "src/esolangs/interpreters/shared/__init__.py": "",
        "src/esolangs/interpreters/shared/aux.py": "from ..other import helper\n",
        "src/esolangs/interpreters/other/unrelated.py": "",
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tmp_path


@pytest.mark.parametrize(
    "module",
    [
        "other.fixture",
        "interpreters.other.fixture",
        "esolangs.interpreters.other.fixture",
    ],
)
def test_relative_transitive_and_cyclic_imports_are_hashed(source_tree, module) -> None:
    sources = leaks._sources(module)  # noqa: SLF001
    assert source_tree / "src/esolangs/interpreters/other/helper.py" in sources
    assert source_tree / "src/esolangs/interpreters/shared/aux.py" in sources
    assert source_tree / "src/esolangs/interpreters/other/unrelated.py" not in sources
    assert len(sources) == len(set(sources))


@pytest.mark.usefixtures("source_tree")
def test_helper_change_selects_its_importer() -> None:
    changed = "src/esolangs/interpreters/shared/aux.py"
    runners = {
        "fixture": ("other.fixture", False),
        "unrelated": ("other.unrelated", False),
    }
    with patch.object(leaks, "_changed_files", return_value=[changed]):
        selected, _ = leaks._select(list(runners), runners)  # noqa: SLF001
    assert selected == ["fixture"]


def test_helper_change_invalidates_a_cached_fingerprint(source_tree) -> None:
    before = leaks._fingerprint("other.fixture", [])  # noqa: SLF001
    helper = source_tree / "src/esolangs/interpreters/shared/aux.py"
    helper.write_text(helper.read_text() + "value = 1\n")
    assert leaks._fingerprint("other.fixture", []) != before  # noqa: SLF001


def test_package_children_are_included(source_tree) -> None:
    sources = leaks._sources("shared")  # noqa: SLF001
    assert source_tree / "src/esolangs/interpreters/shared/aux.py" in sources


@pytest.mark.usefixtures("source_tree")
def test_missing_interpreter_is_not_a_clean_fingerprint() -> None:
    with pytest.raises(FileNotFoundError):
        leaks._sources("missing")  # noqa: SLF001


def test_external_and_attribute_imports_do_not_become_files(source_tree) -> None:
    path = source_tree / "src/esolangs/interpreters/other/fixture.py"
    path.write_text(
        "import json\nfrom pathlib import Path\nfrom .helper import value\n"
    )
    assert Path("json.py") not in leaks._sources("other.fixture")  # noqa: SLF001


def test_package_initializers_are_cache_inputs(source_tree) -> None:
    init = source_tree / "src/esolangs/interpreters/other/__init__.py"
    init.write_text("value = 1\n")
    assert init in leaks._sources("other.fixture")  # noqa: SLF001


def test_removed_helper_cannot_skip_the_sweep(source_tree) -> None:
    helper = source_tree / "src/esolangs/interpreters/shared/aux.py"
    helper.unlink()
    with patch.object(
        leaks, "_changed_files", return_value=[str(helper.relative_to(source_tree))]
    ):
        selected, _ = leaks._select(["fixture"], {"fixture": ("other.fixture", False)})  # noqa: SLF001
    assert selected == ["fixture"]


def test_missing_imported_module_fails_closed(source_tree) -> None:
    source = source_tree / "src/esolangs/interpreters/other/fixture.py"
    source.write_text("from esolangs.interpreters.missing import value\n")
    with pytest.raises(FileNotFoundError, match="imported source"):
        leaks._sources("other.fixture")  # noqa: SLF001
