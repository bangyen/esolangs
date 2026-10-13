"""The dead-definition gate reports what nothing reads and nothing else."""

from pathlib import Path
from typing import Any

from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "checks" / "check_dead_definitions.py"


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
            "src/esolangs/generation/gen.py": (
                "def gen(t):\n    return t\n\n\ndef _old_route(t):\n    return t * 2\n"
            ),
            "src/esolangs/registry.py": (
                "from esolangs.generation.gen import gen\nLANGS = {'g': gen}\n"
            ),
        },
    )
    found = checker.dead_definitions(root)
    assert [(p.name, n) for p, n, _ in found] == [("gen.py", "_old_route")]


def test_an_import_alias_counts_as_a_read(tmp_path: Path) -> None:
    checker = load_script()
    root = _tree(
        tmp_path,
        {
            "src/esolangs/generation/gen.py": "def _parse(t):\n    return t\n",
            "src/esolangs/other.py": (
                "from esolangs.generation.gen import _parse as _p\n\n\n"
                "def run(t):\n    return _p(t)\n"
            ),
        },
    )
    assert checker.dead_definitions(root) == []


def test_a_forward_reference_counts_as_a_read(tmp_path: Path) -> None:
    checker = load_script()
    root = _tree(
        tmp_path,
        {
            "src/esolangs/generation/gen.py": (
                "from typing import Literal\n"
                "_Halt = Literal['halt']\n\n\n"
                "def step(s) -> '_State | _Halt | None':\n    return None\n\n\n"
                "class _State:\n    pass\n"
            ),
            "src/esolangs/other.py": (
                "from esolangs.generation.gen import step\nRUN = step\n"
            ),
        },
    )
    found = checker.dead_definitions(root)
    assert [n for _, n, _ in found] == []


def test_colocated_tests_do_not_keep_dead_runtime_code_alive(tmp_path: Path) -> None:
    checker = load_script()
    root = _tree(
        tmp_path,
        {
            "src/esolangs/languages/tiny/interpreter.py": (
                "def _retired():\n    return 1\n"
            ),
            "src/esolangs/languages/tiny/tests/test_tiny.py": (
                "from esolangs.languages.tiny.interpreter import _retired\n"
                "def test_old():\n    assert _retired() == 1\n"
            ),
        },
    )
    assert [(p.name, name) for p, name, _ in checker.dead_definitions(root)] == [
        ("interpreter.py", "_retired")
    ]
