"""Unit tests for the shared OISC CLI entry point."""

import sys
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.oisc_cli import main_with_limit, run_with_limit


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


class _CountingMachine:
    """A step-capable machine that halts after a fixed number of steps."""

    def __init__(self, steps: int) -> None:
        self.steps = steps
        self.taken = 0

    @property
    def halted(self) -> bool:
        return self.taken >= self.steps

    def step(self) -> None:
        self.taken += 1


def test_run_with_limit_stops_when_the_machine_halts() -> None:
    """A machine that halts inside the limit stops stepping at that point."""
    machine = _CountingMachine(3)
    run_with_limit(machine, 10)
    assert machine.taken == 3


def test_run_with_limit_checks_halted_before_the_first_step() -> None:
    """An already-halted machine is never stepped."""
    machine = _CountingMachine(0)
    run_with_limit(machine, 10)
    assert machine.taken == 0


def test_run_with_limit_raises_past_the_limit() -> None:
    """A machine that never halts raises once the limit is spent."""
    machine = _CountingMachine(1_000)
    with pytest.raises(HaltError) as caught:
        run_with_limit(machine, 5)
    assert str(caught.value) == "execution exceeded the 5-instruction limit"
    assert machine.taken == 5
