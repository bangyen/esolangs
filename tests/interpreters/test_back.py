"""Unit tests for the Back interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.back import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.raises import raises_message


def run_and_capture(code: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestBack:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param(["*"], "0", id="halt_prints_tape"),
            pytest.param(["-*"], "1", id="flip_bit"),
            # + skips the next cell when the current bit is 0.
            pytest.param([">+-*"], "0 0", id="skip_instruction_on_zero"),
            # \ reflects the direction.
            pytest.param(["\\-*"], "1", id="reflect_backslash"),
            # < moves the tape head left when it is not at zero.
            pytest.param([">>-<*"], "0 0 1", id="move_left"),
            # The beam moves by rows too, not only along one line.
            pytest.param(["\\", "-", "*"], "1", id="beam_travels_down_a_column"),
            # A short row keeps its content at the left, and the pad goes right.
            pytest.param(["\\", "\\-*"], "1", id="a_short_line_is_padded_on_the_right"),
        ],
    )
    def test_result(self, code, expected) -> None:
        assert run_and_capture(code) == expected

    def test_blank_only_program_is_empty(self) -> None:
        """Programs of only blank lines are rejected, not crashed on."""

        message = "Back program cannot be empty"
        with raises_message(ValueError, message):
            run_and_capture(["\n"])
        with raises_message(ValueError, message):
            run_and_capture(["   ", "\t"])


class TestStepMachine:
    def test_step_tracks_beam_tape_and_direction(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        machine = _Machine(["-*"], ScriptedIO())
        assert (machine.row, machine.col, machine.a, machine.b) == (0, 0, 0, 1)
        assert machine.tape == (0,)
        machine.step()  # - flips the current bit
        assert machine.tape == (1,)
        machine.step()  # * halts the beam
        assert machine.halted
        assert machine.io.getvalue() == ""  # the dump is the next step's
        machine.step()  # the post-halt step prints the tape
        assert machine.io.getvalue() == "1"
        machine.step()  # stepping again is a no-op; the dump fires once
        assert machine.io.getvalue() == "1"
        assert machine.row == 0

    def test_moving_left_from_cell_zero_grows_the_tape_left(self) -> None:
        """``<`` at the leftmost cell adds a zero cell there, not an underflow."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        machine = _Machine(["-<-*"], ScriptedIO())
        machine.step()  # "-" flips the start cell
        machine.step()  # "<" grows a new cell 0 and lands on it
        assert (machine.cell, machine.tape) == (0, (0, 1))
        machine.step()  # "-" flips the new cell, not the start cell
        assert machine.tape == (1, 1)

    def test_left_of_zero_and_back_keeps_both_cells(self) -> None:
        """The grown cell is distinct from the start cell, and both dump."""
        assert run_and_capture(["-<<>>-*"]) == "0 0 0"
        assert run_and_capture(["-<>*"]) == "0 1"

    def test_moving_right_grows_the_tape_only_at_its_end(self) -> None:
        """``>`` appends a cell when it steps past the last one, once."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        machine = _Machine([">>*"], ScriptedIO())
        assert machine.tape == (0,)
        machine.step()  # past the end: the tape grows
        assert machine.tape == (0, 0)
        machine.step()  # past the new end: it grows again
        assert machine.tape == (0, 0, 0)

        # Re-entering a cell that already exists leaves the tape alone.
        revisit = _Machine(["><>*"], ScriptedIO())
        revisit.step()  # ">" grows to two cells
        assert revisit.tape == (0, 0)
        revisit.step()  # "<" back to cell 0
        revisit.step()  # ">" onto the cell that already exists
        assert revisit.tape == (0, 0), "no cell appended for known ground"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.back import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["-*"]
    halting_program: ClassVar[list[str]] = ["-*"]
    looping_program: ClassVar[list[str]] = ["-"]
