"""Hash caching preserves Pylint's duplicate diagnostics and controls."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_duplicate_code.py"


AST_PROBE = """import sys
from astroid import MANAGER, builder
from pylint.checkers import symilar
from tests.scripts.script_support import load
script = load(__import__('pathlib').Path(sys.argv[1]))
saved_run, saved_process = script.Run, symilar.SimilaritiesChecker.process_module
source = 'import os\\nvalue = 1\\n'
saved_parse, saved_build = symilar.astroid.parse, builder.AstroidBuilder._data_build
def process(_self, node):
    assert symilar.astroid.parse(source) is node
    replacement = symilar.astroid.parse('\\n\\n' + source)
    assert replacement is not node and replacement.body[0].lineno == 3
def run(_args):
    node = builder.AstroidBuilder(MANAGER).string_build(source, 'example')
    symilar.SimilaritiesChecker.process_module(None, node)
    raise ValueError('stop')
symilar.SimilaritiesChecker.process_module, script.Run = process, run
try:
    script.main()
except ValueError as error:
    assert str(error) == 'stop'
assert symilar.astroid.parse is saved_parse
assert builder.AstroidBuilder._data_build is saved_build
assert symilar.SimilaritiesChecker.process_module is process
script.Run = saved_run
symilar.SimilaritiesChecker.process_module = saved_process
sys.argv = sys.argv[1:]
script.main()
"""


@pytest.mark.medium
@pytest.mark.parametrize("disabled", [False, True])
def test_cached_detector_matches_pylint_on_repeated_blocks(
    tmp_path: Path, *, disabled: bool
) -> None:
    block = "\n".join(f"value_{i} = {i}" for i in range(15)) + "\n"
    paths = []
    for index in range(3):
        path = tmp_path / f"example_{index}.py"
        pragma = "# pylint: disable=duplicate-code\n" if disabled else ""
        path.write_text(pragma + "\n" * index + block, encoding="utf-8")
        paths.append(str(path))
    unrelated = tmp_path / "unrelated.py"
    unrelated.write_text("\n".join(f"other_{i} = {i}" for i in range(15)) + "\n")
    paths.append(str(unrelated))
    flags = [
        "--disable=all",
        "--enable=duplicate-code",
        "--min-similarity-lines=10",
        "--ignore-imports=yes",
        "--score=no",
        *paths,
    ]
    baseline, cached = [
        subprocess.run([*cmd, *flags], capture_output=True, text=True, check=False)
        for cmd in (
            (sys.executable, "-m", "pylint"),
            (sys.executable, "-c", AST_PROBE, str(SCRIPT)),
        )
    ]
    assert cached.returncode == baseline.returncode == (0 if disabled else 8)
    assert cached.stdout == baseline.stdout
    assert cached.stderr == baseline.stderr == ""
    assert ("R0801" in cached.stdout) is not disabled
