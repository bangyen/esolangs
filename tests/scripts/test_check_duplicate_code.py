"""Hash caching preserves Pylint's duplicate diagnostics and controls."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_duplicate_code.py"


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
    baseline = subprocess.run(
        [sys.executable, "-m", "pylint", *flags],
        capture_output=True,
        text=True,
        check=False,
    )
    cached = subprocess.run(
        [sys.executable, str(SCRIPT), *flags],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cached.returncode == baseline.returncode == (0 if disabled else 8)
    assert cached.stdout == baseline.stdout
    assert cached.stderr == baseline.stderr == ""
    assert ("R0801" in cached.stdout) is not disabled
