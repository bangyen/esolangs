"""Boolean-function generator for Dimensional.

A bare ``>`` takes its dimension from the byte it stands on (``:260`` parses
none, ``:382`` reads the cell, in ``interpreters/tape_based/dimensional.py``),
so ``d>`` displaces the pointer by the bit read -- dimension 1 for a one, 0 for
a zero; ``{d`` loops on a *coordinate* (``:296``), so the index doubles.

The table is painted, two characters an entry: a trailing zero run is left
unpainted (unvisited cells read 0); an interior run of zeros is a counter
loop where that is shorter, any other entry is painted one by one.
"""

import re
from itertools import groupby

from esolangs.registry._language import Language, Shape
from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, input_weights
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.wrap import (
    _DIMENSIONAL_COMMAND,
    _dimensional,
    balance_score,
    wrap_program,
)

__all__ = ["dimensional"]

_INDEX, _PLANE = 1, 3
_DOUBLE = "{1<1>2>2}{2<2>1}"
_COUNTER, _SPARE = 4, 5
_COUNT_DOUBLE = (
    f"{{{_COUNTER}<{_COUNTER}>{_SPARE}>{_SPARE}}}{{{_SPARE}<{_SPARE}>{_COUNTER}}}"
)
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
    # Skipping the first read's doubling saves 16 characters, 2.2% at n=8:
    # not worth the special case.
    weights, truth_table = input_weights(truth_table, n)
    reads = (_DOUBLE + _READ if weight else "d" for weight in weights)
    index = "".join(reads)
    program = _paint(truth_table) + index + f">{_PLANE}" + "+" * _ASCII_ZERO + "."
    return wrap_program(program, "dimensional", width)


def _paint(truth_table: str) -> str:
    """Write the table along dimension 1 and come back to the origin.

    Two characters an entry either way: ``>1`` for a zero, ``+`` and a bare
    ``>`` for a one, whose ``+`` leaves the 1 that names the index axis.
    Painting stops at the last one, since an unvisited cell already reads 0.
    A long run of zeros is a counter loop (:func:`_advance`); ones are not,
    as a cell is keyed by every nonzero coordinate, counter included.
    """
    last = truth_table.rfind("1")
    if last < 0:
        return ""
    cells = [
        _advance(len(run)) if bit == "0" else "+>" * len(run)
        for bit, group in groupby(truth_table[:last])
        for run in ["".join(group)]
    ]
    return f">{_PLANE}" + "".join(cells) + f"+!{_INDEX}<{_PLANE}"


def _count(count: int) -> str:
    """Return commands making dimension 4 hold ``count``, doubling through 5."""
    unary = f">{_COUNTER}" * count
    if count < 2:
        return unary
    doubled = _count(count // 2) + _COUNT_DOUBLE + f">{_COUNTER}" * (count & 1)
    return min(unary, doubled, key=len)


def _advance(length: int) -> str:
    """Return the shortest commands moving ``length`` along dimension 1.

    ``m`` steps a pass under a counter of ``length // m``, the rest bare.
    """
    best = f">{_INDEX}" * length
    for m in range(1, length // 2 + 1):
        count, rest = divmod(length, m)
        loop = (
            _count(count)
            + f"{{{_COUNTER}<{_COUNTER}"
            + f">{_INDEX}" * m
            + "}"
            + f">{_INDEX}" * rest
        )
        best = min(best, loop, key=len)
    return best


def _dimensional_bare(table: str, n: int) -> str:
    """Program painting the leaf coordinates (axis 2+2i+bit); width 1, n<=2.

    Essential for the width: the shared index form is 102-161 characters
    against this form's 189-437, but wraps no narrower than two columns.

    An ignored input paints nothing.  Before the last essential read its
    ``d`` is overwritten by the next; after it, ``d`` would clobber the leaf,
    so it reads at the leaf and steps off along a fresh axis (``[-]`` fixes
    the dimension) to a second leaf copy.
    """
    weights, painted = input_weights(table, n)
    if not any(weights):
        weights, painted = [1] * n, table
    essential = [i for i, weight in enumerate(weights) if weight]
    m = len(essential)
    last = essential[-1]
    fresh = 2 + 2 * m
    trailing = n - 1 - last
    parts: list[str] = []

    def move(dimension: int, direction: str) -> str:
        return "[-]" + "+" * dimension + direction

    for row, bit in enumerate(painted):
        dimensions = [
            2 + 2 * index + int(value)
            for index, value in enumerate(format(row, f"0{m}b"))
        ] + [fresh] * trailing
        parts.extend(move(dimension, ">") for dimension in dimensions)
        # Leaf values select exit axis zero or one, outside all input axes.
        # Return off-plane until the final move, never erasing a painted leaf.
        parts.append(move(int(bit), ">"))
        parts.extend(move(dimension, "<") for dimension in reversed(dimensions))
        parts.append(move(int(bit), "<"))
    for i in range(n):
        if i in essential:
            parts.append("d" + "+" * (2 + 2 * essential.index(i)) + ">")
        elif i < last:
            parts.append("d")
        else:
            parts.append("d" + move(fresh, ">"))
    parts.append("+" * _ASCII_ZERO + ".")
    return "".join(parts)


def _balance(table: str, default: str) -> str:
    """Balance index tokens above width one and compare bare leaf coordinates."""
    tokens = re.findall(_DIMENSIONAL_COMMAND, default)
    width = balanced_token_width(tokens, minimum=2)
    return min(
        default, dimensional(table, width), dimensional(table, 1), key=balance_score
    )


LANGUAGE = Language(
    "Dimensional",
    "tape_based.dimensional",
    boolean=dimensional,
    # Not a tree: one painted cell per entry along dimension 1.
    shape=Shape.LOOKUP,
    wrap=_dimensional,
    balance=_balance,
)
