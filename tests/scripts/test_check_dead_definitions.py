"""The dead-definition gate reports what nothing reads and nothing else."""

from pathlib import Path
from typing import Any

from tests.scripts.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_dead_definitions.py"


def load_script() -> Any:
    return load(SCRIPT)


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
