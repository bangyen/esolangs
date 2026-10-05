# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
"""Construct terminal ports independently of the geometry compiler."""

from esolangs.interpreters.grid_based.streetcode import _Machine
from esolangs.interpreters.io import ScriptedIO


def junction(width, branch, depth):
    rows = [
        "+" + "-" * width + "+",
        "|" + " " * width + "|",
        "|C" + " " * (width - 2) + ";|",
    ]
    roof = list("+" + "-" * width + "+")
    roof[branch - 1] = "+"
    roof[branch] = roof[branch + 1] = " "
    roof[branch + 2] = "+"
    rows.append("".join(roof))
    for _ in range(depth):
        rows.append(" " * (branch - 1) + "|  |" + " " * (width - branch - 1))
    rows[-1] = rows[-1][:branch] + ";" + rows[-1][branch + 1 :]
    rows.append(" " * (branch - 1) + "+--+" + " " * (width - branch - 1))
    return tuple(rows), (2, width), (len(rows) - 2, branch)


def rotated(rows, point):
    height = len(rows)
    width = len(rows[0])
    translation = str.maketrans("-|", "|-")
    drawing = tuple(
        "".join(rows[height - 1 - r][c] for r in range(height)).translate(translation)
        for c in range(width)
    )
    return drawing, (point[1], height - 1 - point[0])


def check(rows, target, value):
    machine = _Machine._for_run(list(rows), ScriptedIO())
    machine.cells = {0: value}
    for count in range(500):
        if machine.halted:
            assert (machine.row, machine.col) == target, (
                rows,
                value,
                target,
                (machine.row, machine.col),
            )
            assert machine.cp == 0
            assert machine.cells == {0: value}
            return count
        old = (machine.row, machine.col)
        machine.step()
        if not machine.halted:
            assert abs(machine.row - old[0]) + abs(machine.col - old[1]) == 1
    raise AssertionError("finite junction route bound exceeded")
