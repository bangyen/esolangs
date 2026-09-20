"""Build linear-size Piet programs for Boolean truth tables."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from esolangs.raster import Raster

from . import _COLOURS, BLACK

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


def _validate(truth_table: str) -> int:
    """Validate a truth table and return its input count."""
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}"
        )
    if not all(bit in "01" for bit in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    return n


def _push(value: int) -> _Operation:
    return _Operation(_PUSH, value)


def _operations(truth_table: str, inputs: int) -> list[_Operation]:
    """Return stack operations for a linear table lookup."""
    operations: list[_Operation] = []
    for bit in truth_table:
        operations.append(_push(1))
        if bit == "0":
            operations.append(_Operation(_NOT))

    # Accumulate the MSB-first input as a binary row number.
    operations.extend((_push(1), _Operation(_NOT)))
    for _ in range(inputs):
        operations.extend(
            (_push(2), _Operation(_MULTIPLY), _Operation(_IN_NUMBER), _Operation(_ADD))
        )

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


@cache
def generate(truth_table: str) -> Raster:
    """Return a Piet raster computing ``truth_table`` in linear space."""
    inputs = _validate(truth_table)
    operations = _operations(truth_table, inputs)

    # A three-codel initial block reaches row 1.  Its pop is ignored on the
    # empty stack; the final vertical block is entered at its middle codel,
    # so every DP/CC exit is blocked and the program terminates.
    colour = (255, 192, 192)
    blocks: list[tuple[tuple[int, int, int], int]] = []
    colour = _next_colour(colour, _POP)
    for operation in operations:
        blocks.append((colour, operation.size))
        colour = _next_colour(colour, operation.change)

    width = 2 + sum(size for _, size in blocks) + 1
    rows = [[BLACK for _ in range(width)] for _ in range(3)]
    initial = (255, 192, 192)
    rows[0][0] = initial
    rows[1][0] = initial
    rows[1][1] = initial
    x = 2
    for block_colour, size in blocks:
        rows[1][x : x + size] = [block_colour] * size
        x += size
    rows[0][x] = colour
    rows[1][x] = colour
    rows[2][x] = colour
    return Raster(tuple(tuple(row) for row in rows))
