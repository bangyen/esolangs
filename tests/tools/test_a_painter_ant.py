"""Tests for the A Painter Ant Boolean generator.

A Painter Ant has no I/O: the interpreter prints the visited-cell bounding
box, and the Boolean answer is read from a small semantic grid model (the
box output carries no coordinates).  For the supported arities the answer
is the origin's colour after a whole cycle (white is one, black is zero).

Every instantiated program is also run through the real interpreter to
confirm it is a fixed point: the box is identical for any limit that is a
whole number of cycles.
"""

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.booleans.a_painter_ant import a_painter_ant, instantiate

_MOVE = {"n": (0, -1), "e": (1, 0), "s": (0, 1), "w": (-1, 0)}


def _origin_after(program: str, cycles: int = 6) -> int:
    """Origin colour (1 white, 0 black) after ``cycles`` whole cycles."""
    grid: dict[tuple[int, int], int] = {}
    x = y = 0
    for _ in range(cycles * len(program)):
        for command in program:
            if command == "p":
                grid[(x, y)] = 0
            elif command == "P":
                grid[(x, y)] = 1
            else:
                dx, dy = _MOVE[command.lower()]
                if (grid.get((x + dx, y + dy), 0) == 1) == command.isupper():
                    x += dx
                    y += dy
    return grid.get((0, 0), 0)


def _cycle_stable(program: str) -> bool:
    """The interpreter's box is identical for every whole number of cycles."""
    io = ScriptedIO()
    run(program, io, limit=len(program))
    ref = io.getvalue()
    io = ScriptedIO()
    run(program, io, limit=10 * len(program))
    return io.getvalue() == ref


def _check(table: str, bits: list[int]) -> int:
    program = instantiate(a_painter_ant(table), bits)
    assert _cycle_stable(program), f"{table} {bits}: not cycle-stable"
    return _origin_after(program)


def test_one_input_functions() -> None:
    for table in ("00", "01", "10", "11"):
        for bit in (0, 1):
            assert _check(table, [bit]) == int(table[bit]), f"{table} bit {bit}"


def test_all_two_input_functions() -> None:
    for value in range(16):
        table = format(value, "04b")
        for row in range(4):
            bits = [(row >> 1) & 1, row & 1]
            assert _check(table, bits) == int(table[row]), f"{table} bits {bits}"


def test_three_input_rejected() -> None:
    with pytest.raises(ValueError, match="n <= 2"):
        a_painter_ant("00000001")  # AND3


def test_three_input_xor_rejected() -> None:
    with pytest.raises(ValueError, match="n <= 2"):
        a_painter_ant("01101001")  # XOR3


def test_instantiate_complement_placeholders() -> None:
    """{C0} fills with the opposite command of {X0}."""
    assert instantiate("{X0}{C0}", [0]) == "nN"
    assert instantiate("{X0}{C0}", [1]) == "Nn"
