r"""Unit tests for the A Painter Ant interpreter."""

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import EmptyProgramContract


def run_program(code: str, passes: int = 1) -> str:
    r"""Step ``code`` for exactly ``passes`` whole cycles and render."""
    machine = _Machine(code)
    span = len(machine.prog)
    for _ in range(passes * span):
        machine.step()
    return machine.render()


class TestMovement:
    def test_lowercase_moves_on_black(self) -> None:
        # n/e/s/w move one cell onto an.
        # on a black cell, so it marks.
        assert run_program("n") == "o\n."
        assert run_program("s") == ".\no"
        assert run_program("e") == ".o"
        assert run_program("w") == "o."

    def test_uppercase_does_not_move_onto_black(self) -> None:
        # N/E/S/W only move onto white.
        # ant stays on the origin and.
        assert run_program("N") == "o"
        assert run_program("S") == "o"
        assert run_program("E") == "o"
        assert run_program("W") == "o"

    def test_uppercase_moves_onto_white(self) -> None:
        # Paint the cell north of the.
        # it: '@' is the ant resting on.
        assert run_program("nPsN") == "@\n."

    def test_conditional_movement_leaves_ant_in_place(self) -> None:
        # P whites the origin, n leaves.
        # move, so the ant is still on.
        assert run_program("PnN") == "o\n#"


class TestPainting:
    def test_paint_white(self) -> None:
        # The ant rests on the cell it.
        assert run_program("P") == "@"

    def test_paint_black(self) -> None:
        # The origin is already black;.
        assert run_program("p") == "o"

    def test_paint_then_move_writes_the_trail(self) -> None:
        # Each pass paints the current.
        # trail behind the ant is white.
        assert run_program("Pn", 3) == "o\n#\n#\n#"


class TestImplicitLoop:
    def test_program_wraps_after_the_last_instruction(self) -> None:
        # "P n" repeated four times.
        assert run_program("Pn", 4) == "o\n#\n#\n#\n#"

    def test_diamond_example(self) -> None:
        # The wiki's diamond program.
        # diamond, with the east move.
        assert run_program("PnPwPsPe", 3) == ".##\n###\n##.\n.#o"

    def test_run_finds_the_first_repeated_pass(self) -> None:
        r"""``run`` renders at the first pass boundary whose state repeats."""
        io = ScriptedIO()
        run("NPsP", io)
        assert io.getvalue() == run_program("NPsP", 2)
        assert io.getvalue() != run_program("NPsP", 1)


class TestFormat:
    def test_whitespace_is_ignored(self) -> None:
        # P whites the origin, n steps.
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
        lines = output.splitlines()
        # This long walk reaches the.
        # comb.
        # trace from the counterexample.
        assert len(lines) == 5927
        assert {len(line) for line in lines} == {28}
        assert lines[:4] == [
            "###.........................",
            ".#..........................",
            "............................",
            "##..........................",
        ]
        assert lines[-2:] == [
            "@#..........................",
            "#...........................",
        ]


class TestStepMachine:
    def test_step_tracks_ip_grid_and_position(self) -> None:
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine

        machine = _Machine("Pn")
        assert machine.halted is False
        assert machine.ip == 0
        machine.step()  # P whites the origin.
        assert machine.ip == 1
        assert machine.grid[(0, 0)] == 1
        machine.step()  # n moves north.
        assert machine.ip == 0  # wrapped past the last.
        assert (machine.x, machine.y) == (0, -1)

    def test_snapshot_is_a_hashable_complete_state(self) -> None:
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine

        machine = _Machine("Pn")
        first = machine.snapshot()
        assert hash(first) is not None
        machine.step()
        assert machine.snapshot() != first  # the paint changed the state.

    def test_blocked_instruction_loops_and_is_a_cycle(self) -> None:
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # N never fires (all cells.
        assert run_until_halt_or_cycle(_Machine("N")) is False

    def test_generated_boolean_program_is_a_cycle(self) -> None:
        from esolangs.interpreters.grid_based.a_painter_ant import _Machine
        from esolangs.tools.boolean.a_painter_ant import _instantiate_apa, a_painter_ant
        from esolangs.vm import run_until_halt_or_cycle

        program = _instantiate_apa(a_painter_ant("0110"), [1, 0])  # XOR, f=1.
        assert run_until_halt_or_cycle(_Machine(program)) is False


def test_an_empty_program_leaves_the_ant_where_it_started() -> None:
    r"""With no instructions each step returns at once, painting nothing."""
    assert run_program("") == "o"


def test_run_terminates_on_an_empty_program() -> None:
    r"""``run()`` itself, not just the ``_Machine``-driven test helper."""
    io = ScriptedIO()
    run("", io)
    assert io.getvalue() == "o"


class TestContract(EmptyProgramContract):
    r"""The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    empty_output = "o"
