# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
"""Author revision 78016, finite routes, and complete cycle states."""

import pytest

from esolangs.interpreters.grid_based.streetcode import _Machine
from esolangs.interpreters.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters import streetcode_junctions as junctions
from tests.interpreters import streetcode_observer as rectangles


@pytest.mark.parametrize("shard", range(20))
def test_rectangle_traces(shard):
    for index, case in enumerate(rectangles.random_cases(2500)):
        if index % 20 == shard:
            rectangles.check(*case)


@pytest.mark.parametrize(
    "value", [-(1 << 80), -1, 0, 0xD800, 0x10FFFF, 0x110000, 1 << 80]
)
def test_unbounded_output_boundaries(value):
    rectangles.check("  ", "CO", initial={0: value})


def test_static_program_identity():
    left = _Machine._for_run(["+---+", "|   |", "|CI;|", "+---+"], ScriptedIO("A"))
    right = _Machine._for_run(["+---+", "|   |", "|CO;|", "+---+"], ScriptedIO("A"))
    assert left.snapshot() != right.snapshot()


def test_cursorless_cat_progress():
    class Cursorless(ScriptedIO):
        def position(self):
            return 0

    io = Cursorless("AAAAAAB")
    machine = _Machine._for_run(["+----+", "|UOI |", "|CIOU|", "+----+"], io)
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine)
    assert io.reads == 7
    assert io.getvalue() == "AAAAAAB"


@pytest.mark.parametrize(
    ("width", "branch", "depth"),
    [
        (width, branch, depth)
        for width in (8, 10, 14)
        for branch in range(3, width - 3)
        for depth in (2, 4, 8)
    ],
)
def test_geometric_junction_routes(width, branch, depth):
    original, straight, side = junctions.junction(width, branch, depth)
    left = list(original)
    upper = list(left[1])
    upper[1] = ";"
    upper[width] = "C"
    left[1] = "".join(upper)
    lower = list(left[2])
    lower[1] = lower[width] = " "
    left[2] = "".join(lower)
    for rows, zero, nonzero in (
        (original, straight, side),
        (tuple(left), side, (1, 1)),
    ):
        for _turn in range(4):
            for value in (0, 1, -1, 1 << 80):
                junctions.check(rows, zero if value == 0 else nonzero, value)
            old = rows
            rows, zero = junctions.rotated(old, zero)
            _, nonzero = junctions.rotated(old, nonzero)
