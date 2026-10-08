"""Build linear-size Piet programs for Boolean truth tables.

A constant half is folded: the other half is stored and the top bit combines
with the entry.  A repeated subtable is not shared: a strip has no jump, and
copying an entry back costs a depth-sized push (one codel per level), more
than the 1.5-codel entry it replaces.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from esolangs.interpreters.stack_based.piet import _COLOURS, BLACK
from esolangs.raster import Raster
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, SourceKind
from esolangs.tools.helpers import _validate_truth_table, essential_inputs, read_at

Change = tuple[int, int]
Pixel = tuple[int, int, int]

_INITIAL: Pixel = (255, 192, 192)

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
    """``size`` is the codel count; for ``_PUSH`` it is the pushed value."""

    change: Change
    size: int = 1


def _push(value: int) -> _Operation:
    return _Operation(_PUSH, value)


def _literal_product(
    table: str, essential: list[int], inputs: int
) -> list[_Operation] | None:
    """Return a conjunction or its complement, consuming inputs in order.

    One-hot and one-cold tables: Piet++ raster area (3 rows x width, codels)
    is 97.0% / 95.5% smaller than the lookup at n=8 (10 tables each).
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
    operations = [_push(1)]
    for cell in range(inputs):
        operations.append(_Operation(_IN_NUMBER))
        if cell not in literals:
            operations.append(_Operation(_POP))
            continue
        if literals[cell] == 0:
            operations.append(_Operation(_NOT))
        operations.append(_Operation(_MULTIPLY))
    if invert:
        operations.append(_Operation(_NOT))
    operations.append(_Operation(_OUT_NUMBER))
    return operations


def _candidates(truth_table: str, inputs: int) -> list[list[_Operation]]:
    """Return the lookups worth comparing: a literal product, else plain and halved.

    Every input is read, but only the essential ones index the table: an
    ignored input is popped, and the stored table is projected onto the rest.
    """
    essential = essential_inputs(truth_table, inputs)
    truth_table = read_at(truth_table, essential, inputs)
    direct = _literal_product(truth_table, essential, inputs)
    if direct is not None:
        return [direct]
    halved = _half_lookup(truth_table, essential, inputs)
    plain = _lookup(truth_table, essential, inputs)
    return [plain] if halved is None else [plain, halved]


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


def _half_lookup(
    table: str, essential: list[int], inputs: int
) -> list[_Operation] | None:
    """Return the lookup of a table whose one half is constant, or ``None``.

    The first essential bit ``b`` is read before the table and left under it.
    The other half is stored, and ``b`` is rolled back to combine with the
    entry: ``sel * !b`` for a zero upper half, ``!(!sel * !b)`` for a one one.
    Constant half, default strip: -30%/-26% (zero upper half) and -17%/-13%
    (one lower half) at n=7/6, 12 seeded tables; random tables unchanged.
    """
    half = len(table) // 2
    upper = len(set(table[half:])) == 1
    if not upper and len(set(table[:half])) != 1:
        return None
    kept, constant = (
        (table[:half], table[half:]) if upper else (table[half:], table[:half])
    )
    one = constant[0] == "1"
    first = essential[0]
    operations = [
        op for _ in range(first) for op in (_Operation(_IN_NUMBER), _Operation(_POP))
    ]
    operations.append(_Operation(_IN_NUMBER))
    operations.extend(_entries(kept))
    operations.extend(_row_number(essential, inputs, first + 1))
    operations.extend(_select(half))
    if one:
        operations.append(_Operation(_NOT))
    operations.extend(
        (
            _push(half),  # a power of two, which the bounded layouts rebuild
            _push(1),
            _Operation(_ADD),
            _push(1),
            _push(2),
            _Operation(_SUBTRACT),
            _Operation(_ROLL),
        )
    )
    if upper:
        operations.append(_Operation(_NOT))
    operations.append(_Operation(_MULTIPLY))
    if one:
        operations.append(_Operation(_NOT))
    operations.append(_Operation(_OUT_NUMBER))
    return operations


def _next_colour(colour: Pixel, change: Change) -> Pixel:
    hue, lightness = _COLOURS[colour]
    wanted = (hue + change[0]) % 6, (lightness + change[1]) % 3
    return next(
        pixel for pixel, coordinates in _COLOURS.items() if coordinates == wanted
    )


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
    """Return a Piet raster computing ``truth_table``."""
    inputs = _validate_truth_table(truth_table)
    return strip(_operations(truth_table, inputs), _INITIAL, _next_colour)


def piet(truth_table: str, width: int | None = None, *, scale: int = 1) -> Raster:
    """Return a Piet raster computing the table."""
    if width is not None:
        from esolangs.tools.piet.balance import folded

        return folded(truth_table, width).upscaled(scale)
    return _generate(truth_table).upscaled(scale)


LANGUAGE = Language(
    "Piet",
    "stack_based.piet",
    source_kind=SourceKind.RASTER,
    boolean=piet,
    contract=BooleanContract(note="80 pixels per codel, comparable in area to Line"),
)
