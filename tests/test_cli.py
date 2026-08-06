"""Unit tests for the esolangs command-line interface."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from esolangs.cli import main


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


class TestCLIInProcess:
    def test_run_interpreter_in_process(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        program = tmp_path / "prog.exc"
        program.write_text("^<<<<<<^!")
        args = ["esolangs", "esolangs.interpreters.tape_based.excon", str(program)]
        with patch.object(sys, "argv", args):
            main()
        assert capsys.readouterr().out == "A"

    def test_unknown_module_in_process(self, capsys: pytest.CaptureFixture) -> None:
        with patch.object(sys, "argv", ["esolangs", "no.such.module"]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 2
        assert "unknown module" in capsys.readouterr().err


class TestPackageEntryPoint:
    """python -m esolangs dispatches to the CLI via esolangs/__main__.py."""

    def test_run_as_main(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        import runpy

        program = tmp_path / "prog.exc"
        program.write_text("^<<<<<<^!")
        args = ["esolangs", "esolangs.interpreters.tape_based.excon", str(program)]
        with patch.object(sys, "argv", args):
            runpy.run_module("esolangs", run_name="__main__")
        assert capsys.readouterr().out == "A"
