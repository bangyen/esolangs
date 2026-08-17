"""Tests for the A Painter Ant Boolean generator.

A Painter Ant has no I/O: the interpreter prints the visited-cell bounding
box, and the Boolean answer is read from a small semantic grid model (the
box output carries no coordinates).  For ``n <= 2`` the answer is the
origin's colour after a whole cycle (white is one, black is zero); for
``n >= 3`` the answer is the box *height*, which grows strictly with the
number of one-inputs, so every weight-threshold table is decodable.

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


def _box_height(program: str) -> int:
    """Visited-cell bounding-box height after whole cycles (n >= 3 contract)."""
    io = ScriptedIO()
    run(program, io, limit=10 * len(program))
    return io.getvalue().count("\n") + 1


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


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_weight_thresholds(n: int) -> None:
    """Every weight-threshold table is decodable via the box height."""
    import itertools

    for k in range(1, n + 1):
        table = "".join("1" if i.bit_count() >= k else "0" for i in range(2**n))
        template = a_painter_ant(table)
        # the height must distinguish every weight, so the threshold decodes
        heights = set()
        for bits in itertools.product((0, 1), repeat=n):
            program = instantiate(template, list(bits))
            assert _cycle_stable(program), f"{table} {bits}"
            heights.add(_box_height(program))
        # strictly monotone heights -> each weight maps to a distinct height
        assert len(heights) == n + 1, f"n={n} k={k}: heights not distinct"


@pytest.mark.parametrize("n", [3, 4, 5])
def test_weight_threshold_is_correct(n: int) -> None:
    """A threshold table's box height is monotone in the input weight."""
    import itertools

    for k in range(1, n + 1):
        table = "".join("1" if i.bit_count() >= k else "0" for i in range(2**n))
        template = a_painter_ant(table)
        by_weight: dict[int, set[int]] = {}
        for bits in itertools.product((0, 1), repeat=n):
            program = instantiate(template, list(bits))
            by_weight.setdefault(sum(bits), set()).add(_box_height(program))
        heights = [sorted(by_weight[w]) for w in range(n + 1)]
        for w in range(n):
            assert max(heights[w]) <= min(
                heights[w + 1]
            ), f"n={n} k={k}: weight {w} not below weight {w + 1}"


def test_three_input_non_threshold_rejected() -> None:
    import pytest

    # 01101001 is XOR3, not a weight threshold.
    with pytest.raises(ValueError, match="weight-threshold"):
        a_painter_ant("01101001")


def test_large_n_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="n <= 6"):
        a_painter_ant("0" * 128 + "1" * 128)  # n == 8 threshold


def test_instantiate_complement_placeholders() -> None:
    """{C0} fills with the opposite command of {X0}."""
    assert instantiate("{X0}{C0}", [0]) == "nN"
    assert instantiate("{X0}{C0}", [1]) == "Nn"
