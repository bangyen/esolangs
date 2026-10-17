"""Dimensional Boolean program generator: a painted table indexed by the doubled bits.

A bare ``>`` takes its dimension from the byte it stands on (the interpreter's
``>`` arm parses no number and reads the cell instead), so ``d>`` displaces the
pointer by the bit read: dimension 1 for a one, 0 for a zero.  ``{d`` loops on
a *coordinate* (its ``{`` arm), so the index doubles.

The table is painted, two characters an entry: a trailing zero run is left
unpainted (unvisited cells read 0); an interior run of zeros is a counter
loop where that is shorter, any other entry is painted one by one.

Size:
    O(T) for dense tables, O(n) for and; n=10 random 1847: 2,302 chars,
    n=10 and: 375 chars, n=10 majority: 1,993 chars.

Decisions:
    The bare leaf-coordinate form (width 1, n<=2) is 189-437 characters against
    the shared index form's 102-161, kept only because the index form wraps no
    narrower than two columns.  Skipping the first read's doubling saves 16
    characters, 2.2% at n=8: not worth the special case.
"""

import re
from itertools import groupby
from math import isqrt

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import (
    _DIMENSIONAL_COMMAND,
    _dimensional,
    balance_score,
    wrap_program,
)
from esolangs.registry._language import Language, Shape

__all__ = ["dimensional"]

_INDEX, _PLANE = 1, 3
# Double on the return pass: 9 steps per unit instead of 13.
_DOUBLE = "{1<1>2}{2<2>1>1}"
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
    return _program(truth_table, width)


def _program(truth_table: str, width: int | None = None) -> str:
    """Build an indexed lookup or read into scratch and print a fresh literal."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        move = "[-]+++>" if width == 1 and n <= 2 else f">{_PLANE}"
        constant = "d" * n + move + "+" * (_ASCII_ZERO + int(truth_table[0])) + "."
        return wrap_program(constant, "dimensional", width)
    if width == 1 and n <= 2:
        return wrap_program(_dimensional_bare(truth_table, n), "dimensional", width)
    # An ignored input is a bare ``d``: the next read overwrites its byte.
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
    # Doubling saves nothing on random tables (n=7..10), 11.4% (n=12) and 20.6%
    # (n=14) of chars on and, 13.4% on a threshold at n=14.
    unary = f">{_COUNTER}" * count
    if count < 2:
        return unary
    doubled = _count(count // 2) + _COUNT_DOUBLE + f">{_COUNTER}" * (count & 1)
    return min(unary, doubled, key=len)


def _advance(length: int) -> str:
    """Move along dimension 1 using unary, counted, or balanced-stride commands."""
    bare = f">{_INDEX}" * length
    # The loop saves 83.7% of chars on and at n=10, 73% on a threshold, 13.5% on
    # majority, 0% on random tables.  Nine is the first zero run that a counted
    # loop shortens.
    if length < 9:
        return bare

    def counted(stride: int) -> str:
        count, rest = divmod(length, stride)
        return (
            _count(count)
            + f"{{{_COUNTER}<{_COUNTER}"
            + f">{_INDEX}" * stride
            + "}"
            + f">{_INDEX}" * rest
        )

    return min(bare, counted(max(1, isqrt(length))), key=len)


def _dimensional_bare(table: str, n: int) -> str:
    """Program painting the leaf coordinates (axis 2+2i+bit); width 1, n<=2.

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
    """Compare the token-balanced and one-column layouts of one construction."""
    tokens = re.findall(_DIMENSIONAL_COMMAND, default)
    width = balanced_token_width(tokens, minimum=2)
    return min(
        default,
        _program(table, width),
        _program(table, 1),
        key=balance_score,
    )


LANGUAGE = Language(
    "Dimensional",
    "dimensional",
    category="tape_based",
    boolean=dimensional,
    # Not a tree: one painted cell per entry along dimension 1.
    shape=Shape.LOOKUP,
    wrap=_dimensional,
    balance=_balance,
)
