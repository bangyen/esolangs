"""Unit tests for the A Painter Ant interpreter.

Tests cover the conditional movement instructions, painting, the implicit
program loop, whitespace handling, and the documented grid dump that makes
the no-I/O language observable.
"""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.a_painter_ant import run


def run_program(code: str, limit: int = 10_000) -> str:
    io = ScriptedIO()
    run(code, io, limit=limit)
    return io.getvalue()


class TestMovement:
    def test_lowercase_moves_on_black(self) -> None:
        # n/e/s/w move one cell onto an adjacent black cell.
        assert run_program("n", 1) == "#\n#\n"
        assert run_program("s", 1) == "#\n#\n"
        assert run_program("e", 1) == "##\n"
        assert run_program("w", 1) == "##\n"

    def test_uppercase_does_not_move_onto_black(self) -> None:
        # N/E/S/W only move onto white cells; all cells start black.
        assert run_program("N", 1) == "#\n"
        assert run_program("S", 1) == "#\n"
        assert run_program("E", 1) == "#\n"
        assert run_program("W", 1) == "#\n"

    def test_uppercase_moves_onto_white(self) -> None:
        # Paint the cell north of the start white, return, then N moves onto it.
        assert run_program("nPsN", 4) == ".\n#\n"

    def test_conditional_movement_leaves_ant_in_place(self) -> None:
        # P whites the origin, n leaves it, N finds a black cell north: no move.
        assert run_program("PnN", 3) == "#\n.\n"


class TestPainting:
    def test_paint_white(self) -> None:
        assert run_program("P", 1) == ".\n"

    def test_paint_black(self) -> None:
        # The origin is already black; p leaves it black.
        assert run_program("p", 1) == "#\n"

    def test_paint_then_move_writes_the_trail(self) -> None:
        # Each pass paints the current cell white, then steps north.
        assert run_program("Pn", 6) == "#\n.\n.\n.\n"


class TestImplicitLoop:
    def test_program_wraps_after_the_last_instruction(self) -> None:
        # "P n" repeated four times paints a northward trail of three whites.
        assert run_program("Pn", 8) == "#\n.\n.\n.\n.\n"

    def test_diamond_example(self) -> None:
        # The wiki's diamond program paints the start of an ever-growing
        # diamond, with the east move blocked by the newly painted cell.
        assert run_program("PnPwPsPe", 12) == "#..\n#..\n"


class TestFormat:
    def test_empty_program(self) -> None:
        assert run_program("") == "#\n"

    def test_whitespace_is_ignored(self) -> None:
        # P whites the origin, n steps onto the still-black north cell.
        assert run_program(" P \n n ", 2) == "#\n.\n"

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
