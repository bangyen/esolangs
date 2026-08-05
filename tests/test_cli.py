"""Unit tests for the esolangs command-line interface."""

import subprocess
import sys
from pathlib import Path


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "esolangs.cli", *args],
        capture_output=True,
        text=True,
    )


class TestCLI:
    def test_unknown_module(self) -> None:
        result = run_cli("no.such.module")
        assert result.returncode == 2
        assert "unknown module" in result.stderr

    def test_missing_argument(self) -> None:
        result = run_cli()
        assert result.returncode == 2

    def test_run_interpreter(self, tmp_path: Path) -> None:
        program = tmp_path / "prog.exc"
        program.write_text("^<<<<<<^!")
        result = run_cli("esolangs.interpreters.tape_based.excon", str(program))
        assert result.returncode == 0
        assert result.stdout == "A"
