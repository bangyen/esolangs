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

    def test_halted_is_always_false(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(".", IO())
        assert machine.halted is False
        for _ in range(5):
            machine.step()
        assert machine.halted is False

    def test_step_wraps_at_code_end(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!.", IO())
        machine.step()  # !
        assert machine.ind == 1
        assert machine.tape == [1]
        machine.step()  # .
        assert machine.ind == 0  # wrapped past the last instruction

    def test_cycle_is_detected(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # "." never changes state, so the snapshot repeats immediately
        assert run_until_halt_or_cycle(_Machine(".", IO())) is False
        assert run_until_halt_or_cycle(_Machine("<", IO())) is False

    def test_snapshot_excludes_pass_count(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        # "." is a no-op when acc is 0, so the state after one whole pass
        # (len(code) steps) equals the initial state -- the pass count must
        # not be part of snapshot, or every state would be unique and the
        # cycle detector would never fire.
        machine = _Machine("..", IO())
        before = machine.snapshot()
        machine.step()
        machine.step()  # one whole pass
        assert machine.snapshot() == before
