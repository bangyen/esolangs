"""The prose-density gate counts comments and docstring body lines."""

from pathlib import Path
from typing import Any

import pytest

from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "checks" / "check_comment_density.py"


def load_script() -> Any:
    return load(SCRIPT)


def test_a_docstring_body_counts_and_its_first_paragraph_does_not() -> None:
    script = load_script()
    source = (
        "def f():\n"
        '    """Contract.\n'
        "\n"
        "    A note that goes on.\n"
        '    """\n'
        "    return 1\n"
    )
    assert script.density(source) == (2, 1)


def test_an_over_commentated_file_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    path = tmp_path / "noisy.py"
    path.write_text("\n".join(["# a note"] * 12 + ["value = 1", ""]))
    assert script.main([str(path)]) == 1
    assert "code lines per prose line" in capsys.readouterr().out


def test_a_lean_file_passes(tmp_path: Path) -> None:
    script = load_script()
    path = tmp_path / "lean.py"
    path.write_text("\n".join(f"value_{i} = {i}" for i in range(20)) + "\n")
    assert script.main([str(path)]) == 0


def test_a_file_under_the_prose_floor_is_skipped(tmp_path: Path) -> None:
    script = load_script()
    path = tmp_path / "tiny.py"
    # Nine prose lines is below MIN_PROSE, so the ratio is noise, not a finding.
    path.write_text("\n".join(["# a note"] * 9 + ["value = 1", ""]))
    assert script.main([str(path)]) == 0
