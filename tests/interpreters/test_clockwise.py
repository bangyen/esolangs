"""Unit tests for the Clockwise interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.interpreters.grid_based.clockwise import run
from esolangs.interpreters.io import IO, ScriptedIO


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestClockwise:
    def test_output_character(self) -> None:
        """Pushing bits 1000001 outputs 'A'."""
        code = ["+;S;S;S;S;S;+;R", "R             R"]
        assert run_and_capture(code) == "A"

    def test_truth_machine_zero(self) -> None:
        """Truth-machine with input 0 halts after outputting '0'."""
        code = ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"]
        assert run_and_capture(code, inputs=["0"]) == "0"

    def test_empty_program_rejected(self) -> None:
        """An empty program is malformed."""
        with pytest.raises(ValueError, match="empty"):
            run_and_capture([])

    def test_unclosed_ring_rejected(self) -> None:
        """A pointer that walks off the ring is a malformed program."""
        with pytest.raises(ValueError, match="not closed"):
            run_and_capture(["+;S"])


class TestStepMachine:
    def test_step_tracks_position_heading_and_accumulator(self) -> None:
        from esolangs.interpreters.grid_based.clockwise import _Machine

        machine = _Machine(["+;S;S;S;S;S;+;R", "R             R"], IO())
        assert (machine.row, machine.col, machine.r, machine.acc) == (0, 0, 0, 0)
        machine.step()  # + at the origin: acc 1, head right
        assert (machine.row, machine.col, machine.r, machine.acc) == (0, 1, 0, 1)
        machine.step()  # ; at row 0, col 1: parity bit queued
        assert (machine.row, machine.col, machine.r) == (0, 2, 0)
        machine.step()  # S at row 0, col 2: acc zeroed
        assert (machine.row, machine.col, machine.r, machine.acc) == (0, 3, 0, 0)

    def test_halting_ring_is_detected(self) -> None:
        from esolangs.interpreters.grid_based.clockwise import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine(["+;S;S;S;S;S;+;R", "R             R"], IO())
        assert run_until_halt_or_cycle(machine) is True

    def test_looping_ring_is_detected_as_a_cycle(self) -> None:
        """A ring whose orbit never re-enters the origin loops forever.

        The halt condition is a return to the origin with a non-zero heading,
        so this ring's closed orbit is a finite-state cycle the detector can
        prove without waiting out a timeout.
        """
        from esolangs.interpreters.grid_based.clockwise import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        machine = _Machine(["SS?R ", "+?+S-", "R!!RS"], IO())
        assert run_until_halt_or_cycle(machine) is False

    def test_snapshot_includes_the_input_bits_and_their_rotation(self) -> None:
        """A consuming ``.`` rotates the input bit list, changing the snapshot."""
        from esolangs.interpreters.grid_based.clockwise import _Machine

        machine = _Machine(
            ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"],
            ScriptedIO("0"),
        )
        assert machine.io.position() == 1  # the whole input line was read up front
        for _ in range(3):
            machine.step()  # no '.' yet: the input is untouched
        before = machine.snapshot()
        machine.step()  # the '.' at (4,0) consumes the first bit and rotates it
        assert machine.snapshot() != before
        assert "".join(machine.inp) == "1100000"


def test_reading_with_no_input_is_eof() -> None:
    """Bits are read up front, so an empty queue is exhausted input."""
    from esolangs.interpreters.io import ScriptedIO

    with pytest.raises(EOFError):
        run(".", ScriptedIO("\n"))
