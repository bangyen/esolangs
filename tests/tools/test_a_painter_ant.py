"""Tests for the A Painter Ant Boolean generator.

A Painter Ant has no I/O: the interpreter prints the visited-cell bounding
box, and the Boolean answer is read from a small semantic grid model (the
box output carries no coordinates).  The answer is the colour of the cell
the ant lands on at the end of a cycle (white is one, black is zero), read
after any whole number of cycles since every instantiated program is a
cycle-stable fixed point.

The generator supports every one- and two-input table (``n == 1`` pads to a
two-input table with the second input fixed to zero).  ``n >= 3`` is an open
problem (``docs/roadmap.md``) and raises.
"""

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.booleans.a_painter_ant import a_painter_ant, instantiate

_MOVE = {"n": (0, -1), "e": (1, 0), "s": (0, 1), "w": (-1, 0)}


def _landing_after(program: str, cycles: int = 6) -> int:
    """Landing cell colour (1 white, 0 black) after ``cycles`` cycles.

    Whitespace is ignored (the interpreter strips it), and the ant runs the
    program in an implicit loop; after each whole cycle the ant rests on its
    output leaf, whose colour is the Boolean answer.
    """
    prog = [c for c in program if not c.isspace()]
    grid: dict[tuple[int, int], int] = {}
    x = y = 0
    for _ in range(cycles * len(prog)):
        for command in prog:
            if command == "p":
                grid[(x, y)] = 0
            elif command == "P":
                grid[(x, y)] = 1
            else:
                dx, dy = _MOVE[command.lower()]
                if (grid.get((x + dx, y + dy), 0) == 1) == command.isupper():
                    x += dx
                    y += dy
    return grid.get((x, y), 0)


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
    return _landing_after(program)


def test_all_two_input_functions() -> None:
    """Every two-input table is exact and cycle-stable for every input."""
    for value in range(16):
        table = format(value, "04b")
        for row in range(4):
            bits = [(row >> 1) & 1, row & 1]
            assert _check(table, bits) == int(table[row]), f"{table} bits {bits}"


def test_xor() -> None:
    """XOR (0110) is one of the expressible tables."""
    assert _check("0110", [0, 0]) == 0
    assert _check("0110", [0, 1]) == 1
    assert _check("0110", [1, 0]) == 1
    assert _check("0110", [1, 1]) == 0


def test_nand() -> None:
    """NAND (1110) is expressible."""
    assert _check("1110", [0, 0]) == 1
    assert _check("1110", [1, 1]) == 0


def test_constant_tables() -> None:
    """Constant zero and one are expressible."""
    assert _check("0000", [0, 0]) == 0
    assert _check("0000", [1, 1]) == 0
    assert _check("1111", [0, 0]) == 1
    assert _check("1111", [1, 1]) == 1


def test_template_has_input_placeholders() -> None:
    """The template carries {X0} and {X1}, not hardcoded bits."""
    template = a_painter_ant("0110")
    assert "{X0}" in template
    assert "{X1}" in template


def test_leaf_paint_uses_space_for_zero() -> None:
    """A zero leaf is left unpainted (space), a one leaf is painted P.

    The generator never paints a cell black (no ``p``), which is what keeps
    every instantiated program a monotone, cycle-stable fixed point.
    """
    template = a_painter_ant("0110")  # f(1,1)=0, f(0,0)=0, f(1,0)=1, f(0,1)=1
    assert " " in template  # zero leaves are spaces
    # no paint-black anywhere in any instantiated program
    program = instantiate(template, [1, 1])
    assert "p" not in program


def test_all_one_input_functions() -> None:
    """Every one-input table is exact and cycle-stable for both inputs.

    n == 1 is supported by fixing the padded second input to zero and using
    the n == 2 construction with b1 == 0 (see :func:`a_painter_ant`).
    """
    for value in range(4):
        table = format(value, "02b")
        for bit in [0, 1]:
            assert _check(table, [bit]) == int(table[bit]), f"table {table} bit {bit}"


def test_instantiate_one_bit_fills_single_placeholder() -> None:
    """An n == 1 template carries only {X0}, filled per bit."""
    template = a_painter_ant("01")  # f(0)=0, f(1)=1
    assert "{X0}" in template
    assert "{X1}" not in template
    assert instantiate(template, [1]) == template.replace("{X0}", "WWwWWEEe")
    assert instantiate(template, [0]) == template.replace("{X0}", "NENEESWw")


def test_three_input_rejected() -> None:
    """n >= 3 is an open problem and raises."""
    with pytest.raises(ValueError, match="open problem"):
        a_painter_ant("00000001")  # AND3


def test_three_input_xor_rejected() -> None:
    with pytest.raises(ValueError, match="open problem"):
        a_painter_ant("01101001")  # XOR3


def test_three_input_construction_is_cycle_one_exact() -> None:
    """The n == 3 single-row construction is exact for cycle 1 on every table.

    The template is ``head + n + body + {X0}{X1}{X2} + Pn``: the head paints
    the eight leaves on ``y = -2`` at ``x = +-2 +-4 +-8`` (symmetric across
    the y-axis), the body paints the routing row ``y = -1``, every input
    routes east/west by its weight (2, 4, 8) on the painted row, and the
    ``Pn`` landing trick reads the leaf.  Cycle 2 is still open
    (``docs/a_painter_ant_generator.md``), so :func:`a_painter_ant` keeps
    raising for ``n >= 3``.
    """
    from itertools import product

    from esolangs.tools.booleans.a_painter_ant import _body, _head

    def _landing_after_one_cycle(program: str) -> int:
        """Landing cell colour after exactly one cycle (unstable past it)."""
        prog = [c for c in program if not c.isspace()]
        grid: dict[tuple[int, int], int] = {}
        x = y = 0
        for command in prog:
            if command == "p":
                grid[(x, y)] = 0
            elif command == "P":
                grid[(x, y)] = 1
            else:
                dx, dy = _MOVE[command.lower()]
                if (grid.get((x + dx, y + dy), 0) == 1) == command.isupper():
                    x += dx
                    y += dy
        return grid.get((x, y), 0)

    for value in range(256):
        table = format(value, "08b")
        template = _head(table, [0, 0, 0]) + "n" + _body(3) + "{X0}{X1}{X2}" + "Pn"
        for bits in product([0, 1], repeat=3):
            program = instantiate(template, list(bits))
            assert _landing_after_one_cycle(program) == int(
                table[bits[0] * 4 + bits[1] * 2 + bits[2]],
            ), f"table {table} bits {bits}"


def test_bad_table_rejected() -> None:
    with pytest.raises(ValueError, match="power-of-two"):
        a_painter_ant("011")


def test_non_binary_rejected() -> None:
    with pytest.raises(ValueError, match="only '0' and '1'"):
        a_painter_ant("0123")


def test_instantiate_fills_bits() -> None:
    """{X0} fills nn/ss and {X1} fills WWwWWEEe/NENEESWw per bit."""
    template = a_painter_ant("0110")
    assert instantiate(template, [1, 1]) == template.replace(
        "{X0}",
        "nn",
    ).replace("{X1}", "WWwWWEEe")
    assert instantiate(template, [0, 0]) == template.replace(
        "{X0}",
        "ss",
    ).replace("{X1}", "NENEESWw")
