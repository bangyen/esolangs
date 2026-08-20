"""Unit tests for the shared OISC CLI entry point."""

import sys
from unittest.mock import patch

from esolangs.interpreters.oisc_cli import main_with_limit


def test_runs_program_file_with_default_limit(tmp_path, capsys) -> None:
    program = tmp_path / "program.txt"
    program.write_text("-1 4 0 -7 65")

    calls = []

    def run(data, io, limit=10_000):
        calls.append((data, limit))
        io.print_char("A")

    with patch.object(sys, "argv", ["prog", str(program)]):
        main_with_limit(run)

    assert calls == [("-1 4 0 -7 65", 10_000)]
    assert capsys.readouterr().out == "A"


def test_runs_program_file_with_explicit_limit(tmp_path) -> None:
    program = tmp_path / "program.txt"
    program.write_text("0 0 0 0")

    calls = []

    def run(data, _io, limit=10_000):
        calls.append((data, limit))

    with patch.object(sys, "argv", ["prog", str(program), "50"]):
        main_with_limit(run)

    assert calls == [("0 0 0 0", 50)]


def test_no_arguments_does_nothing() -> None:
    calls = []

    def run(data, _io, limit=10_000):
        calls.append((data, limit))

    with patch.object(sys, "argv", ["prog"]):
        main_with_limit(run)

    assert calls == []
