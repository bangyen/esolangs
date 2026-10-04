"""Installed CLI and worker paths preserve Unicode and distinguish failures."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import esolangs

pytestmark = pytest.mark.medium


def test_worker_thread_loads_unicode_path(tmp_path: Path) -> None:
    source = tmp_path / "λ program.sophie"
    source.write_text("#λ,", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(
            esolangs.run, "Sophie", source, isolated=True, max_output=1
        )
        assert result.result(timeout=10) == "λ"


@pytest.mark.parametrize(
    ("source", "options", "code", "output", "diagnostic"),
    [
        ("#λ,", [], 0, "λ", ""),
        ("#λ,,", ["--max-output", "1"], 1, "λ\n", "output limit"),
        (";", [], 1, "", "input"),
    ],
)
def test_cli_unicode_path_and_error(
    tmp_path: Path,
    source: str,
    options: list[str],
    code: int,
    output: str,
    diagnostic: str,
) -> None:
    path = tmp_path / "λ program.sophie"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "esolangs",
            "run",
            "--isolated",
            *options,
            "Sophie",
            str(path),
        ],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == code
    assert result.stdout == output
    assert diagnostic in result.stderr.lower()
