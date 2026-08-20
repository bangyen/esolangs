"""Unit tests for the Suffolk interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.suffolk import run


def run_and_capture(code: str, limit: int = 1) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, limit=limit, io=IO())
    return buffer.getvalue()


class TestSuffolk:
    def test_count_and_output(self) -> None:
        """66 increments of the counter then a print yields 'A'."""
        assert run_and_capture("!" * 66 + "<.") == "A"

    def test_other_value(self) -> None:
        assert run_and_capture("!" * 70 + "<.") == "E"

    def test_output_requires_accumulator(self) -> None:
        """A . with no accumulated value prints nothing."""
        assert run_and_capture("!.") == ""

    def test_no_halt_without_instruction(self) -> None:
        """Programs without a halt run until the loop limit is reached."""
        assert run_and_capture("!!!!") == ""

    def test_move_right(self) -> None:
        """> moves the pointer to a new tape cell."""
        assert run_and_capture("!!!!!!!!>!><<<<<<<<<.!") == "@"

    def test_input(self) -> None:
        """, reads input into the accumulator."""
        buffer = io.StringIO()
        with patch("builtins.input", return_value="B"), redirect_stdout(buffer):
            run(",.", limit=1, io=IO())
        assert buffer.getvalue() == "A"

    def test_empty_program_rejected(self) -> None:
        """An empty program is malformed."""
        import pytest

        with pytest.raises(ValueError, match="empty"):
            run("", IO())


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!", IO())
        before = machine.snapshot()
        machine.step()  # ! sets the current cell from the accumulator
        assert machine.snapshot() != before
        assert machine.tape == [1]

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("!", IO())) is True

    def test_bounded_pass_limit_always_halts(self) -> None:
        # Suffolk has no backward jump: the pass counter strictly increases
        # toward `limit`, so every program halts and none can cycle.
        from esolangs.interpreters.tape_based.suffolk import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("!!!!", IO(), limit=3)) is True

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!", IO(), limit=0)
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.tape == [0]
