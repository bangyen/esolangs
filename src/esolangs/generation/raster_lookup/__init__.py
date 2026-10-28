"""Build linear-size raster lookups for Boolean truth tables.

A constant half is not folded ([ablations.halved_lookup]); a repeated
subtable is not shared: a strip has no jump, and copying an entry back costs a
depth-sized push (one codel per level), more than the 1.5-codel entry it
replaces.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from esolangs.generation.helpers import essential_inputs, read_at
from esolangs.raster import Raster
from esolangs.runtime.codels import BLACK, COLOURS

Change = tuple[int, int]
Pixel = tuple[int, int, int]


_INITIAL: Pixel = (255, 192, 192)

_PUSH = (0, 1)
_POP = (0, 2)
_ADD = (1, 0)
_SUBTRACT = (1, 1)
_MULTIPLY = (1, 2)
_NOT = (2, 2)
_POINTER = (3, 1)
_ROLL = (4, 1)
_IN_NUMBER = (4, 2)
_OUT_NUMBER = (5, 1)


@dataclass(frozen=True)
class _Operation:
    """``size`` is the codel count; for ``_PUSH`` it is the pushed value."""

    change: Change
    size: int = 1


def _push(value: int) -> _Operation:
    return _Operation(_PUSH, value)


def _literal_product(
    table: str, essential: list[int], inputs: int
) -> list[_Operation] | None:
    """Return a conjunction or its complement, consuming inputs in order.

    One-hot and one-cold tables: the raster area (3 rows x width, codels)
    is 97.0% / 95.5% smaller than the lookup at n=8 (10 tables each).
    Seeding with the first literal and reading from the entry block cut n=8
    strips from 39,168 to 34,560 codels (-11.76%, all 512 such tables).
    """
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
    operations = [] if essential else [_push(1)]
    for cell in range(inputs):
        operations.append(_Operation(_IN_NUMBER))
        if cell not in literals:
            operations.append(_Operation(_POP))
            continue
        if literals[cell] == 0:
            operations.append(_Operation(_NOT))
        if cell != essential[0]:
            operations.append(_Operation(_MULTIPLY))
    if invert:
        operations.append(_Operation(_NOT))
    operations.append(_Operation(_OUT_NUMBER))
    return operations


def _candidates(truth_table: str, inputs: int) -> list[list[_Operation]]:
    """Return the lookups worth comparing: a literal product, else the plain one.

    Every input is read, but only the essential ones index the table: an
    ignored input is popped, and the stored table is projected onto the rest.
    """
    essential = essential_inputs(truth_table, inputs)
    truth_table = read_at(truth_table, essential, inputs)
    direct = _literal_product(truth_table, essential, inputs)
    if direct is not None:
        return [direct]
    return [_lookup(truth_table, essential, inputs)]


def _operations(truth_table: str, inputs: int) -> list[_Operation]:
    """Return the shortest strip of commands for the table."""
    return min(_candidates(truth_table, inputs), key=_area)


def _area(operations: list[_Operation]) -> int:
    return sum(operation.size for operation in operations)


def _row_number(essential: list[int], inputs: int, start: int) -> list[_Operation]:
    """Read inputs ``start`` on into a row number, MSB first, popping ignored ones."""
    operations = [_push(1), _Operation(_NOT)]
    for i in range(start, inputs):
        if i in essential:
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
    return operations


def _select(size: int) -> list[_Operation]:
    """Roll the entry at the row number to the top of ``size`` stacked entries.

    roll expects [..., depth, rolls].  Swap the table past the row number, then
    -(row + 1) rotates the requested entry to the top.
    """
    return [
        _push(size),
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
    ]


def _entries(table: str) -> list[_Operation]:
    operations: list[_Operation] = []
    for bit in table:
        operations.append(_push(1))
        if bit == "0":
            operations.append(_Operation(_NOT))
    return operations


def _lookup(table: str, essential: list[int], inputs: int) -> list[_Operation]:
    """Return the table pushed whole and the row number rolled to the top."""
    return [
        *_entries(table),
        *_row_number(essential, inputs, 0),
        *_select(len(table)),
        _Operation(_OUT_NUMBER),
    ]


def _next_colour(colour: Pixel, change: Change) -> Pixel:
    hue, lightness = COLOURS[colour]
    wanted = (hue + change[0]) % 6, (lightness + change[1]) % 3
    return next(
        pixel for pixel, coordinates in COLOURS.items() if coordinates == wanted
    )


def strip(
    operations: list[_Operation],
    initial: Pixel,
    next_colour: Callable[[Pixel, Change], Pixel],
) -> Raster:
    """Lay ``operations`` out as one row of blocks, block traversal rules.

    A three-codel initial block reaches row 1.  It supplies the first read
    or an ignored pop; the final vertical block is entered at its middle codel,
    so every DP/CC exit is blocked and the program terminates.
    """
    blocks: list[tuple[Pixel, int]] = []
    first_read = operations[0].change == _IN_NUMBER
    colour = next_colour(initial, _IN_NUMBER if first_read else _POP)
    if first_read:
        operations = operations[1:]
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
