"""The dead-definition gate reports what nothing reads and nothing else.

Two routes and a reorder catalog lived on for months with only their own
tests reading them.  This pins the three judgements the checker has to get
right to be a gate rather than a nuisance: a planted unread name in
``tools/`` is reported; a name read only through an import alias is not; a
name read only inside a string annotation is not.  The tree itself is
judged by the ``verify.py`` step, not here: the scan is 1.7s.
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_dead_definitions.py"


def load_script() -> object:
    """Import the checker as a module, mirroring the other script tests."""
    spec = importlib.util.spec_from_file_location("check_dead_definitions", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (tmp_path / "scripts").mkdir(exist_ok=True)
    return tmp_path


def test_a_planted_unread_name_is_reported(tmp_path: Path) -> None:
    checker = load_script()
    root = _tree(
        tmp_path,
        {
            "src/esolangs/tools/gen.py": (
                "def gen(t):\n    return t\n\n\ndef _old_route(t):\n    return t * 2\n"
            ),
            "src/esolangs/registry.py": (
                "from esolangs.tools.gen import gen\nLANGS = {'g': gen}\n"
            ),
        },
    )
    found = checker.dead_definitions(root)  # type: ignore[attr-defined]
    assert [(p.name, n) for p, n, _ in found] == [("gen.py", "_old_route")]


def test_an_import_alias_counts_as_a_read(tmp_path: Path) -> None:
    checker = load_script()
    root = _tree(
        tmp_path,
        {
            "src/esolangs/tools/gen.py": "def _parse(t):\n    return t\n",
            "src/esolangs/other.py": (
                "from esolangs.tools.gen import _parse as _p\n\n\n"
                "def run(t):\n    return _p(t)\n"
            ),
        },
    )
    assert checker.dead_definitions(root) == []  # type: ignore[attr-defined]


def test_a_forward_reference_counts_as_a_read(tmp_path: Path) -> None:
    checker = load_script()
    root = _tree(
        tmp_path,
        {
            "src/esolangs/tools/gen.py": (
                "from typing import Literal\n"
                "_Halt = Literal['halt']\n\n\n"
                "def step(s) -> '_State | _Halt | None':\n    return None\n\n\n"
                "class _State:\n    pass\n"
            ),
            "src/esolangs/other.py": (
                "from esolangs.tools.gen import step\nRUN = step\n"
            ),
        },
    )
    found = checker.dead_definitions(root)  # type: ignore[attr-defined]
    assert [n for _, n, _ in found] == []
