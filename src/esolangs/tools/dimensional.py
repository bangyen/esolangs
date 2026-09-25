"""Boolean-function generator for Dimensional.

A bare ``>`` takes its dimension from the byte it stands on (``:260`` parses
none, ``:382`` reads the cell, in ``interpreters/tape_based/dimensional.py``),
so ``d>`` displaces the pointer by the bit read -- dimension 1 for a one, 0 for
a zero; ``{d`` loops on a *coordinate* (``:296``), so the index doubles.
"""

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["dimensional"]

_INDEX, _PLANE = 1, 3
_DOUBLE = "{1<1>2>2}{2<2>1}"
_READ = "d>!0"


def dimensional(truth_table: str) -> str:
    """Build a Dimensional program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first; the
    inputs arrive one per line and the answer prints as a digit.
    """
    n = _validate_truth_table(truth_table)
    index = _READ + (_DOUBLE + _READ) * (n - 1)
    return _paint(truth_table) + index + f">{_PLANE}" + "+" * _ASCII_ZERO + "."


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
