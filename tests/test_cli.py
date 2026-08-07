"""Unit tests for the esolangs command-line interface."""

import subprocess
import sys
from pathlib import Path

import esolangs


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "esolangs.cli", *args],
        capture_output=True,
        text=True,
    )


def test_list() -> None:
    result = run_cli("list")
    assert result.returncode == 0
    assert "Sophie" in result.stdout


def test_generate() -> None:
    result = run_cli("generate", "Sophie", "Hi")
    assert result.returncode == 0
    assert esolangs.run("Sophie", result.stdout) == "Hi"


def test_generate_unknown_language() -> None:
    result = run_cli("generate", "NoSuchLanguage", "x")
    assert result.returncode == 2
    assert "unknown language" in result.stderr


def test_run(tmp_path: Path) -> None:
    program = tmp_path / "prog.soph"
    program.write_text(esolangs.generate("Sophie", "Hi"))
    result = run_cli("run", "Sophie", str(program))
    assert result.returncode == 0
    assert result.stdout == "Hi"


def test_run_missing_file() -> None:
    result = run_cli("run", "Sophie", "/no/such/file")
    assert result.returncode == 2
    assert "cannot read" in result.stderr


def test_unknown_command() -> None:
    result = run_cli("no.such.command")
    assert result.returncode == 2
    assert "unknown command" in result.stderr


def test_no_arguments() -> None:
    result = run_cli()
    assert result.returncode == 2


class TestPackageEntryPoint:
    """python -m esolangs dispatches to the CLI via esolangs/__main__.py."""

    def test_run_as_main(self, capsys) -> None:
        import runpy

        args = ["esolangs", "generate", "Sophie", "Hi"]
        with __import__("unittest.mock").mock.patch.object(sys, "argv", args):
            runpy.run_module("esolangs", run_name="__main__")
        out = capsys.readouterr().out
        assert esolangs.run("Sophie", out) == "Hi"
