"""Build linear-size Piet programs for Boolean truth tables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from esolangs.interpreters.stack_based.piet import _COLOURS, BLACK
from esolangs.raster import Raster
from esolangs.tools.helpers import _validate_truth_table, essential_inputs, read_at

Change = tuple[int, int]

_PUSH = (0, 1)
_POP = (0, 2)
_ADD = (1, 0)
_SUBTRACT = (1, 1)
_MULTIPLY = (1, 2)
_NOT = (2, 2)
_ROLL = (4, 1)
_IN_NUMBER = (4, 2)
_OUT_NUMBER = (5, 1)


@dataclass(frozen=True)
class _Operation:
    change: Change
    size: int = 1


def _push(value: int) -> _Operation:
    return _Operation(_PUSH, value)


def _literal_product(
    table: str, essential: list[int], inputs: int
) -> list[_Operation] | None:
    """Return a conjunction or its complement, consuming inputs in order."""
    if table.count("1") == 1:
        row, invert = table.index("1"), False
    elif table.count("0") == 1:
        row, invert = table.index("0"), True
    else:
        return None
    literals = {
        cell: (row >> (len(essential) - position - 1)) & 1
        for position, cell in enumerate(essential)
    }
    operations = [_push(1)]
    for cell in range(inputs):
        operations.append(_Operation(_IN_NUMBER))
        if cell not in literals:
            operations.append(_Operation(_POP))
        else:
            if literals[cell] == 0:
                operations.append(_Operation(_NOT))
            operations.append(_Operation(_MULTIPLY))
    if invert:
        operations.append(_Operation(_NOT))
    operations.append(_Operation(_OUT_NUMBER))
    return operations


def _operations(truth_table: str, inputs: int) -> list[_Operation]:
    """Return a literal product when possible, otherwise a linear lookup.

    Every input is read, but only the essential ones index the table: an
    ignored input is popped, and the stored table is projected onto the rest.
    """
    essential = essential_inputs(truth_table, inputs)
    kept = set(essential)
    truth_table = read_at(truth_table, essential, inputs)
    direct = _literal_product(truth_table, essential, inputs)
    if direct is not None:
        return direct
    operations: list[_Operation] = []
    for bit in truth_table:
        operations.append(_push(1))
        if bit == "0":
            operations.append(_Operation(_NOT))

    # Accumulate the MSB-first input as a binary row number.
    operations.extend((_push(1), _Operation(_NOT)))
    for i in range(inputs):
        if i in kept:
            operations.extend(
                (
                    _push(2),
                    _Operation(_MULTIPLY),
                    _Operation(_IN_NUMBER),
                    _Operation(_ADD),
                )
            )
        else:
            operations.extend((_Operation(_IN_NUMBER), _Operation(_POP)))

    # roll expects [..., depth, rolls].  Swap T past the row number, then
    # -(row + 1) rotates the requested table entry to the top.
    operations.extend(
        (
            _push(len(truth_table)),
            _push(2),
            _push(1),
            _Operation(_ROLL),
            _push(1),
            _Operation(_ADD),
            _push(1),
            _push(2),
            _Operation(_SUBTRACT),
            _Operation(_MULTIPLY),
            _Operation(_ROLL),
            _Operation(_OUT_NUMBER),
        )
    )
    return operations


def _next_colour(colour: tuple[int, int, int], change: Change) -> tuple[int, int, int]:
    hue, lightness = _COLOURS[colour]
    wanted = (hue + change[0]) % 6, (lightness + change[1]) % 3
    return next(
        pixel for pixel, coordinates in _COLOURS.items() if coordinates == wanted
    )


Pixel = tuple[int, int, int]


def strip(
    operations: list[_Operation],
    initial: Pixel,
    next_colour: Callable[[Pixel, Change], Pixel],
) -> Raster:
    """Lay ``operations`` out as one row of blocks, Piet traversal rules.

    A three-codel initial block reaches row 1.  Its pop is ignored on the
    empty stack; the final vertical block is entered at its middle codel,
    so every DP/CC exit is blocked and the program terminates.
    """
    blocks: list[tuple[Pixel, int]] = []
    colour = next_colour(initial, _POP)
    for operation in operations:
        blocks.append((colour, operation.size))
        colour = next_colour(colour, operation.change)

    width = 2 + sum(size for _, size in blocks) + 1
    rows = [[BLACK for _ in range(width)] for _ in range(3)]
    rows[0][0] = rows[1][0] = rows[1][1] = initial
    x = 2
    for block_colour, size in blocks:
        rows[1][x : x + size] = [block_colour] * size
        x += size
    rows[0][x] = rows[1][x] = rows[2][x] = colour
    return Raster(tuple(tuple(row) for row in rows))


@cache
def _generate(truth_table: str) -> Raster:
    """Return a Piet raster computing ``truth_table`` in linear space."""
    inputs = _validate_truth_table(truth_table)
    return strip(_operations(truth_table, inputs), (255, 192, 192), _next_colour)


def piet(truth_table: str, width: int | None = None, *, scale: int = 1) -> Raster:
    """Return a Piet raster computing the table."""
    if width is not None:
        from esolangs.tools.piet.balance import folded

        return folded(truth_table, width).upscaled(scale)
    return _generate(truth_table).upscaled(scale)
