"""Boolean-function generator for Dimensional.

A bare ``>`` takes its dimension from the byte it stands on (``:260`` parses
none, ``:382`` reads the cell, in ``interpreters/tape_based/dimensional.py``),
so ``d>`` displaces the pointer by the bit read -- dimension 1 for a one, 0 for
a zero; ``{d`` loops on a *coordinate* (``:296``), so the index doubles.
"""

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, input_weights
from esolangs.tools.wrap import wrap_program

__all__ = ["dimensional"]

_INDEX, _PLANE = 1, 3
_DOUBLE = "{1<1>2>2}{2<2>1}"
_READ = "d>!0"


def dimensional(truth_table: str, width: int | None = None) -> str:
    """Build a Dimensional program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    inputs arrive one per line and the answer prints as a digit. Width one
    paints leaf coordinates through two inputs; larger tables retain the index.
    """
    n = _validate_truth_table(truth_table)
    if width == 1 and n <= 2:
        return wrap_program(_dimensional_bare(truth_table, n), "dimensional", width)
    # An ignored input is a bare ``d``: the next read overwrites its byte.
    # The first read needs no doubling.
    weights, truth_table = input_weights(truth_table, n)
    reads = (_DOUBLE + _READ if weight else "d" for weight in weights)
    index = "".join(reads).replace(_DOUBLE, "", 1)
    program = _paint(truth_table) + index + f">{_PLANE}" + "+" * _ASCII_ZERO + "."
    return wrap_program(program, "dimensional", width)


def _paint(truth_table: str) -> str:
    """Write the table along dimension 1 and come back to the origin.

    Two characters an entry either way: ``>1`` for a zero, ``+`` and a bare
    ``>`` for a one, whose ``+`` leaves the 1 that names the index axis.
    Painting stops at the last one, since an unvisited cell already reads 0.
    """
    last = truth_table.rfind("1")
    if last < 0:
        return ""
    cells = ["+>" if bit == "1" else f">{_INDEX}" for bit in truth_table[:last]]
    return f">{_PLANE}" + "".join(cells) + f"+!{_INDEX}<{_PLANE}"


def _dimensional_bare(table: str, n: int) -> str:
    """Paint small leaf coordinates while preserving their exit-cell values."""
    parts: list[str] = []

    def move(dimension: int, direction: str) -> str:
        return "[-]" + "+" * dimension + direction

    for row, bit in enumerate(table):
        dimensions = [
            2 + 2 * index + int(value)
            for index, value in enumerate(format(row, f"0{n}b"))
        ]
        parts.extend(move(dimension, ">") for dimension in dimensions)
        # Leaf values select exit axis zero or one, outside all input axes.
        # Return off-plane until the final move, never erasing a painted leaf.
        parts.append("[-]" + "+" * int(bit) + ">")
        parts.extend(move(dimension, "<") for dimension in reversed(dimensions))
        parts.append(move(int(bit), "<"))
    parts.extend("d" + "+" * (2 + 2 * index) + ">" for index in range(n))
    parts.append("+" * _ASCII_ZERO + ".")
    return "".join(parts)
