"""Unit tests for the Back interpreter."""

from functools import partial
from typing import ClassVar

from esolangs.languages.back.interpreter import _Machine as Back
from esolangs.languages.back.interpreter import run
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_growth
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_printing
from tests.support.raises import raises_message

run_and_capture = partial(run_printing, run)


class TestBack:
    def test_blank_only_program_is_empty(self) -> None:
        """Programs of only blank lines are rejected, not crashed on."""

        message = "Back program cannot be empty"
        with raises_message(ValueError, message):
            run_and_capture(["\n"])
        with raises_message(ValueError, message):
            run_and_capture(["   ", "\t"])


class TestStepMachine:
    def test_step_tracks_beam_tape_and_direction(self) -> None:
        machine = Back(["-*"], ScriptedIO())
        assert (machine.row, machine.col, machine.a, machine.b) == (0, 0, 0, 1)
        assert machine.tape == (0,)
        machine.step()  # - flips the current bit
        assert machine.tape == (1,)
        before = machine.workspace_snapshot()
        machine.step()  # * halts the beam
        stopped = machine.workspace_snapshot()
        assert stopped.parts[:6] == before.parts[:6]
        assert stopped.parts[6:8] == (True, False)
        assert machine.halted
        assert machine.io.getvalue() == ""  # the dump is the next step's
        machine.step()  # the post-halt step prints the tape
        assert machine.io.getvalue() == "1"
        dumped = machine.workspace_snapshot()
        assert dumped.parts[:7] == stopped.parts[:7]
        assert dumped.parts[7] is True
        machine.step()  # stepping again is a no-op; the dump fires once
        assert machine.io.getvalue() == "1"
        assert machine.row == 0

    def test_moving_left_from_cell_zero_grows_the_tape_left(self) -> None:
        """``<`` at the leftmost cell adds a zero cell there, not an underflow."""
        machine = Back(["-<-*"], ScriptedIO())
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
        machine = Back([">>*"], ScriptedIO())
        assert machine.tape == (0,)
        machine.step()  # past the end: the tape grows
        assert machine.tape == (0, 0)
        machine.step()  # past the new end: it grows again
        assert machine.tape == (0, 0, 0)

        # Re-entering a cell that already exists leaves the tape alone.
        revisit = Back(["><>*"], ScriptedIO())
        revisit.step()  # ">" grows to two cells
        assert revisit.tape == (0, 0)
        revisit.step()  # "<" back to cell 0
        revisit.step()  # ">" onto the cell that already exists
        assert revisit.tape == (0, 0), "no cell appended for known ground"


def _machine(code: object) -> object:
    return Back(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["-*"]
    halting_program: ClassVar[list[str]] = ["-*"]
    looping_program: ClassVar[list[str]] = ["-"]


def test_the_heading_is_part_of_the_code_position() -> None:
    # Back's position is (row, col, a, b): two visits to one square
    # travelling different ways are not the same point in the program.
    machine = Back([">"], ScriptedIO())
    assert isinstance(machine.ip, tuple)
    assert len(machine.ip) == 4
    assert run_until_halt_or_growth(machine) is False
    from .oracle_checks import check_raw_back

    check_raw_back()
