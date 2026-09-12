r"""Unit tests for the Back interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.back import run
from tests.interpreters.contract import CycleContract, SnapshotContract


def run_and_capture(code: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestBack:
    def test_halt_prints_tape(self) -> None:
        assert run_and_capture(["*"]) == "0"

    def test_flip_bit(self) -> None:
        assert run_and_capture(["-*"]) == "1"

    def test_move_right(self) -> None:
        assert run_and_capture([">-*"]) == "0 1"

    def test_flip_twice(self) -> None:
        assert run_and_capture([">--*"]) == "0 0"

    def test_skip_instruction_on_zero(self) -> None:
        r"""+ skips the next cell when the current bit is 0."""
        assert run_and_capture([">+-*"]) == "0 0"

    def test_reflect_backslash(self) -> None:
        r"""\ reflects the direction."""
        assert run_and_capture(["\\-*"]) == "1"

    def test_reflect_slash(self) -> None:
        r"""/ reflects the direction."""
        assert run_and_capture(["/-*"]) == "1"

    def test_move_left(self) -> None:
        r"""< moves the tape head left when it is not at zero."""
        assert run_and_capture([">>-<*"]) == "0 0 1"

    def test_move_left_lands_on_the_previous_cell(self) -> None:
        r"""< steps back exactly one cell, and the cell it lands on is used."""
        assert run_and_capture([">-<-*"]) == "1 1"

    def test_beam_travels_down_a_column(self) -> None:
        r"""The beam moves by rows too, not only along one line."""
        assert run_and_capture(["\\", "-", "*"]) == "1"

    def test_slash_reflects_the_beam(self) -> None:
        r"""/ turns the beam, rather than letting it carry straight on."""
        assert run_and_capture(["/*", "--"]) == "1"

    def test_skip_moves_the_beam_by_a_whole_row(self) -> None:
        r"""+ steps the beam along its heading, rows included."""
        assert run_and_capture(["\\", "+", "-", "*"]) == "0"

    def test_blank_only_program_is_empty(self) -> None:
        r"""Programs of only blank lines are rejected, not crashed on."""
        import pytest

        message = r"^Back program cannot be empty$"
        with pytest.raises(ValueError, match=message):
            run_and_capture(["\n"])
        with pytest.raises(ValueError, match=message):
            run_and_capture(["   ", "\t"])

    def test_a_short_line_is_padded_on_the_right(self) -> None:
        r"""A short row keeps its content at the left, and the pad goes right."""
        assert run_and_capture(["\\", "\\-*"]) == "1"


class TestStepMachine:
    def test_a_fresh_machine_reports_a_boolean(self) -> None:
        r"""``halted`` starts as False itself, not merely as something falsey."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        assert _Machine(["-*"], ScriptedIO()).halted is False

    def test_step_tracks_beam_tape_and_direction(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        machine = _Machine(["-*"], ScriptedIO())
        assert (machine.row, machine.col, machine.a, machine.b) == (0, 0, 0, 1)
        assert machine.tape == (0,)
        machine.step()  # - flips the current bit.
        assert machine.tape == (1,)
        machine.step()  # * halts the beam.
        assert machine.halted
        assert machine.io.getvalue() == ""  # the dump is the next step's.
        machine.step()  # the post-halt step prints the.
        assert machine.io.getvalue() == "1"
        machine.step()  # stepping again is a no-op;.
        assert machine.io.getvalue() == "1"
        assert machine.row == 0

    def test_moving_left_from_cell_zero_stays_put(self) -> None:
        r"""``<`` at the leftmost cell is a no-op, not an underflow."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        machine = _Machine(["<-*"], ScriptedIO())
        assert machine.cell == 0
        machine.step()  # "<" with nowhere to go.
        assert machine.cell == 0
        machine.step()  # "-" flips the cell the.
        assert machine.tape[0] == 1, "the flip landed on cell 0"

    def test_moving_right_grows_the_tape_only_at_its_end(self) -> None:
        r"""``>`` appends a cell when it steps past the last one, once."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        machine = _Machine([">>*"], ScriptedIO())
        assert machine.tape == (0,)
        machine.step()  # past the end: the tape grows.
        assert machine.tape == (0, 0)
        machine.step()  # past the new end: it grows.
        assert machine.tape == (0, 0, 0)

        # Re-entering a cell that.
        revisit = _Machine(["><>*"], ScriptedIO())
        revisit.step()  # ">" grows to two cells.
        assert revisit.tape == (0, 0)
        revisit.step()  # "<" back to cell 0.
        revisit.step()  # ">" onto the cell that.
        assert revisit.tape == (0, 0), "no cell appended for known ground"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.back import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["-*"]
    halting_program: ClassVar[list[str]] = ["-*"]
