"""Catalogue evidence follows construction imports, not neighboring files."""

import os
from pathlib import Path

import pytest

from tests.generators.source_support import construction_symbols


@pytest.fixture
def sources(tmp_path: Path) -> Path:
    tools = tmp_path / "esolangs/generation"
    tools.mkdir(parents=True)
    (tools / "helpers.py").write_text(
        "def constant_span_test(table):\n    return table[0]\n"
        "def subtree_ids(table):\n    return table\n"
        "def essential_inputs(table):\n    return subtree_ids(table)\n"
    )
    (tools / "emit.py").write_text(
        "from .helpers import constant_span_test as fold, subtree_ids\n"
        "def emit(table):\n    return fold(table)\n"
        "def unused(table):\n    return subtree_ids(table)\n"
    )
    (tools / "export.py").write_text("from .emit import emit as builder\n")
    return tmp_path


def test_module_and_package_have_the_same_evidence(sources: Path) -> None:
    code = (
        "from esolangs.generation.export import builder\n"
        "def generate(table):\n    return builder(table)\n"
    )
    module = sources / "generator.py"
    module.write_text(code)
    package = sources / "generator/__init__.py"
    package.parent.mkdir()
    package.write_text(code)
    (sources / "unrelated.py").write_text("def subtree_ids(table): return table\n")
    expected = {"generate", "emit", "constant_span_test"}
    assert construction_symbols(module, sources, "generate") == expected
    assert construction_symbols(package, sources, "generate") == expected


def test_module_alias_reaches_the_called_helper(sources: Path) -> None:
    path = sources / "generator.py"
    path.write_text(
        "import esolangs.generation.emit as emitter\n"
        "def generate(table):\n    return emitter.emit(table)\n"
    )
    assert construction_symbols(path, sources, "generate") == {
        "generate",
        "emit",
        "constant_span_test",
    }


@pytest.mark.parametrize(
    "code",
    [
        "def generate(fold):\n    return fold('01')\n",
        "def generate(table: fold):\n    return table\n",
        "def generate(table):\n    return (lambda fold: fold(table))(str)\n",
    ],
)
def test_shadowed_or_annotated_helpers_are_not_evidence(
    sources: Path, code: str
) -> None:
    path = sources / "generator.py"
    path.write_text(
        "from esolangs.generation.helpers import constant_span_test as fold\n" + code
    )
    assert construction_symbols(path, sources, "generate") == {"generate"}


def test_dependency_detection_does_not_establish_emitted_sharing(sources: Path) -> None:
    path = sources / "generator.py"
    path.write_text(
        "from esolangs.generation.helpers import essential_inputs\n"
        "def generate(table):\n    return essential_inputs(table)\n"
    )
    assert construction_symbols(path, sources, "generate") == {
        "generate",
        "essential_inputs",
    }


def test_removing_a_called_helper_changes_the_evidence(sources: Path) -> None:
    path = sources / "generator.py"
    path.write_text(
        "from esolangs.generation.emit import emit\n"
        "def generate(table):\n    return emit(table)\n"
    )
    assert "constant_span_test" in construction_symbols(path, sources, "generate")
    (sources / "esolangs/generation/emit.py").write_text(
        "def emit(table): return table\n"
    )
    assert "constant_span_test" not in construction_symbols(path, sources, "generate")


def test_package_member_module_reaches_only_the_selected_function(
    sources: Path,
) -> None:
    path = sources / "generator.py"
    path.write_text(
        "from esolangs.generation import emit as emitter\n"
        "def generate(table):\n    return emitter.emit(table)\n"
    )
    assert construction_symbols(path, sources, "generate") == {
        "generate",
        "emit",
        "constant_span_test",
    }


def test_content_cache_sees_same_size_edits_with_unchanged_mtime(sources: Path) -> None:
    path = sources / "generator.py"
    path.write_text(
        "from esolangs.generation.emit import emit\n"
        "def generate(table):\n    return emit(table)\n"
    )
    helper = sources / "esolangs/generation/emit.py"
    original = helper.read_text()
    stat = helper.stat()
    assert "constant_span_test" in construction_symbols(path, sources, "generate")
    helper.write_text("def emit(table): return table\n".ljust(len(original)))
    os.utime(helper, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert helper.stat().st_size == stat.st_size
    assert helper.stat().st_mtime_ns == stat.st_mtime_ns
    assert construction_symbols(path, sources, "generate") == {"generate", "emit"}
