"""Unit tests for the A Painter Ant interpreter."""

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import _Machine, run
from esolangs.interpreters.grid_based.a_painter_ant import _Machine as _AntMachine
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import EmptyProgramContract


def run_program(code: str, passes: int = 1) -> str:
    """Step ``code`` for exactly ``passes`` whole cycles and render."""
    machine = _Machine(code)
    span = len(machine.prog)
    for _ in range(passes * span):
        machine.step()
    return machine.render()


class TestMovement:
    def test_lowercase_moves_on_black(self) -> None:
        # n/e/s/w move one cell onto an adjacent black cell; 'o' is the ant
        # on a black cell, so it marks where the move ended.
        assert run_program("n") == "o\n."
        assert run_program("s") == ".\no"
        assert run_program("e") == ".o"
        assert run_program("w") == "o."

    def test_uppercase_does_not_move_onto_black(self) -> None:
        # N/E/S/W only move onto white cells; all cells start black, so the
        # ant stays on the origin and the box never grows past it.
        assert run_program("N") == "o"
        assert run_program("S") == "o"
        assert run_program("E") == "o"
        assert run_program("W") == "o"

    def test_uppercase_moves_onto_white(self) -> None:
        # Paint the cell north of the start white, return, then N moves onto
        # it: '@' is the ant resting on a white cell.
        assert run_program("nPsN") == "@\n."

    def test_conditional_movement_leaves_ant_in_place(self) -> None:
        # P whites the origin, n leaves it, N finds a black cell north: no
        # move, so the ant is still on the white origin ('#' below it).
        assert run_program("PnN") == "o\n#"


class TestPainting:
    def test_paint_then_move_writes_the_trail(self) -> None:
        # Each pass paints the current cell white, then steps north, so the
        # trail behind the ant is white ('#') and the ant sits on black.
        assert run_program("Pn", 3) == "o\n#\n#\n#"


class TestImplicitLoop:
    def test_program_wraps_after_the_last_instruction(self) -> None:
        # "P n" repeated four times paints a northward trail of four whites.
        assert run_program("Pn", 4) == "o\n#\n#\n#\n#"

    def test_diamond_example(self) -> None:
        # The wiki's diamond program paints the start of an ever-growing
        # diamond, with the east move blocked by the newly painted cell.
        assert run_program("PnPwPsPe", 3) == ".##\n###\n##.\n.#o"

    def test_run_finds_the_first_repeated_pass(self) -> None:
        """``run`` renders at the first pass boundary whose state repeats."""
        io = ScriptedIO()
        run("NPsP", io)
        assert io.getvalue() == run_program("NPsP", 2)
        assert io.getvalue() != run_program("NPsP", 1)


class TestFormat:
    def test_unknown_instruction_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown instruction"):
            run_program("Px", 10)


class TestStepMachine:
    def test_step_tracks_ip_grid_and_position(self) -> None:
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine

        machine = _Machine("Pn")
        assert machine.halted is False
        assert machine.ip == 0
        machine.step()  # P whites the origin
        assert machine.ip == 1
        assert machine.grid[(0, 0)] == 1
        machine.step()  # n moves north
        assert machine.ip == 0  # wrapped past the last instruction
        assert (machine.x, machine.y) == (0, -1)

    def test_snapshot_is_a_hashable_complete_state(self) -> None:
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine

        machine = _Machine("Pn")
        first = machine.snapshot()
        assert hash(first) is not None
        machine.step()
        assert machine.snapshot() != first  # the paint changed the state

    def test_blocked_instruction_loops_and_is_a_cycle(self) -> None:
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # N never fires (all cells start black), so the run revisits state.
        assert run_until_halt_or_cycle(_Machine("N")) is False


class TestContract(EmptyProgramContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    empty_output = "o"


class TestPainterAntDumpsOnce:
    def test_stepping_an_interrupted_machine_again_does_not_redump(self) -> None:
        """The picture is printed once, however often the machine is stepped."""
        io = ScriptedIO()
        machine = _AntMachine("Pn", io)
        machine.interrupt()
        machine.step()
        first = io.getvalue()
        assert first
        machine.step()
        machine.step()
        assert io.getvalue() == first
