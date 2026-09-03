"""Unit tests for the A Painter Ant interpreter.

Tests cover the conditional movement instructions, painting, the implicit
program loop, whitespace handling, and the documented grid dump that makes
the no-I/O language observable.
"""

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import EmptyProgramContract


def run_program(code: str, passes: int = 1) -> str:
    """Step ``code`` for exactly ``passes`` whole cycles and render.

    ``run()`` itself has no pass count any more -- it steps until the state
    repeats at a boundary, which for a program that never settles (most of
    the ones below: a single ``n`` walks onto a fresh cell forever) would
    not return.  This is the direct replacement for what ``cycles=`` used
    to pin: drive the machine the same number of passes the old default
    argument would have run, then read the same render ``run()`` prints.
    """
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
    def test_paint_white(self) -> None:
        # The ant rests on the cell it just painted white.
        assert run_program("P") == "@"

    def test_paint_black(self) -> None:
        # The origin is already black; p leaves it black.
        assert run_program("p") == "o"

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
        """``run`` renders at the first pass boundary whose state repeats.

        ``NPsP`` is not stable after one pass -- its render only settles
        once pass 2 repeats pass 1's state -- so a version of ``run`` that
        rendered after a single pass regardless would show a picture the
        program does not actually keep drawing.  This pins the render
        against ``run_program`` stepped exactly to the pass where the
        repeat lands, rather than to an arbitrary later one: any pass count
        from there on renders the same, so agreeing with pass 2 and
        disagreeing with pass 1 is the sharpest check available.
        """
        io = ScriptedIO()
        run("NPsP", io)
        assert io.getvalue() == run_program("NPsP", 2)
        assert io.getvalue() != run_program("NPsP", 1)


class TestFormat:
    def test_whitespace_is_ignored(self) -> None:
        # P whites the origin, n steps onto the still-black north cell.
        assert run_program(" P \n n ") == "o\n#"

    def test_unknown_instruction_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown instruction"):
            run_program("Px", 10)

    def test_counter_example_runs(self) -> None:
        counter = """\
PePePePePePePePePePePePePePePePePePePePePePePePePePe
PEpW
ePWsPN
EpWSpN
WsPN
ESpNWePW
sss
ePwPsPN"""
        output = run_program(counter, 2000)
        assert output  # runs without error and dumps a grid
        assert len(output.splitlines()) >= 1


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

    def test_generated_boolean_program_is_a_cycle(self) -> None:
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine
        from esolangs.tools.boolean.a_painter_ant import _instantiate_apa, a_painter_ant
        from esolangs.vm import run_until_halt_or_cycle

        program = _instantiate_apa(a_painter_ant("0110"), [1, 0])  # XOR, f=1
        assert run_until_halt_or_cycle(_Machine(program)) is False


def test_an_empty_program_leaves_the_ant_where_it_started() -> None:
    """With no instructions each step returns at once, painting nothing.

    The grid is still dumped, because that is how the language is made
    observable at all -- so what an empty program shows is the ant's own
    starting cell and nothing else.
    """
    assert run_program("") == "o"


def test_run_terminates_on_an_empty_program() -> None:
    """``run()`` itself, not just the ``_Machine``-driven test helper.

    An empty program has no pass to take (``span == 0``), so the inner
    step loop is a no-op and the very first boundary snapshot already
    equals the starting one -- the general Brent's loop breaks on its
    first iteration without needing a special case.  ``run_program``
    above never calls ``run`` at all (it drives ``_Machine`` directly),
    so this is the only place that path is exercised.
    """
    io = ScriptedIO()
    run("", io)
    assert io.getvalue() == "o"


class TestContract(EmptyProgramContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    empty_output = "o"
