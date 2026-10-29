"""Piet++ Boolean program generator: the table lives in pixels, read by address.

The table is never pushed: Piet++'s ``Read`` fetches a pixel at an offset
from the codel just entered, and a pixel is a 24-bit number.  Row 2 of a
three-row image holds ``2**k`` table bits per pixel (bit ``b`` of pixel ``a``
is row ``a * 2**k + b``, ``k`` of the last essential inputs).  Row 1 is the
program: the first ``m - k`` essential inputs fold by Horner into the pixel
address, ``Read`` loads the pixel from the codel below-and-right, and the
last ``k`` inputs square up ``2**b`` (``p = p * p * (1 + bit)``).  Divide,
mod 2, print.  The data pixel's red byte is 1, a non-palette value that no
block ever absorbs, so no wall is needed.  The IP never enters row 2: the
last block is three tall, entered in its middle, and every exit is black.

Size:
    ``3 * max(L, x + T/2**k + 2)`` codels for ``T = 2**m`` rows, ``L`` the
    program (about 14k + 4(m - k)) and ``x`` the read column, so linear in T
    with a slope of 3/16; n=10 parity: 270 codels.

Decisions:
    * ``k`` is the least-area of 2, 3, 4: ``k = 4`` fills 16 of a pixel's 24
      bits (a larger ``p`` is not a pixel), and costs more program than
      pixels below n = 8.
    * No black row between program and data: the white-sliding non-palette
      pixels are reachable only from the final block, which is walled.
"""

from __future__ import annotations

from functools import cache

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.languages.piet_plus_plus.interpreter import _COMMANDS, _STEP
from esolangs.raster import Raster
from esolangs.registry._language import Language, SourceKind

Pixel = tuple[int, int, int]
#: A block of ``size`` codels, then the command run on leaving it.
type _Op = tuple[int, str]

_BLACK: Pixel = (0, 0, 0)
_DELTA = {name: delta for delta, name in _COMMANDS.items()}
_START: Pixel = (0, 2 * _STEP, 0)
#: Red byte of a data pixel: not 0, 55, AA or FF, so never a palette colour.
_TAG = 1
_MOST_LOW = 4


def _next_colour(colour: Pixel, command: str) -> Pixel:
    """Apply ``command``'s delta, keeping green at level 1 or 2 (never black)."""
    dr, dg, db = _DELTA[command]
    red, green, blue = (level // _STEP for level in colour)
    return (
        (red + dr) % 4 * _STEP,
        (green if dg == 0 else 3 - green) * _STEP,
        (blue + db) % 4 * _STEP,
    )


def _program(inputs: int, essential: list[int], low: int) -> tuple[list[_Op], int, int]:
    """Return the ops, the index of ``read`` and the offset the read adds.

    The first ``len(essential) - low`` essential inputs form the pixel
    address; the last ``low`` form the bit position.  The start block is 3
    codels, so with no address it pushes the offset 3 itself.
    """
    ops: list[_Op] = []
    split = len(essential) - low
    address, bits = essential[:split], essential[split:]
    read = offset = 0
    if not address:
        ops += [(3, "push_int"), (1, "push_int")]
        read, offset = len(ops), 3
        ops.append((1, "read"))
    folded = 0
    for cell in range(inputs):
        if cell in address:
            ops += [(1, "dup"), (1, "add")] if folded else []
            ops.append((1, "in_integer"))
            ops += [(1, "add")] if folded else []
            folded += 1
            if folded == len(address):
                ops.append((1, "push_int"))
                read = len(ops)
                ops.append((1, "read"))
        elif cell in bits:
            if cell != bits[0]:
                ops += [(1, "dup"), (1, "multiply")]
            ops += [(1, "in_integer"), (1, "push_int"), (1, "add")]
            ops += [(1, "multiply")] if cell != bits[0] else []
        else:
            ops += [(1, "in_integer"), (1, "pop")]
    ops += [(1, "divide"), (2, "push_int"), (1, "mod"), (1, "out_integer")]
    return ops, read, offset


def _constant(inputs: int, bit: str) -> list[_Op]:
    ops: list[_Op] = [(1, "in_integer"), (1, "pop")] * inputs
    return [
        *ops,
        (1, "push_int"),
        *([(1, "not")] if bit == "0" else []),
        (1, "out_integer"),
    ]


def _pixels(rows: str, low: int) -> list[Pixel]:
    """Pack ``2**low`` rows per pixel: bit ``b`` of pixel ``a`` is row ``a<<low|b``."""
    width = 1 << low
    values = (
        sum(int(rows[a + b] == "1") << b for b in range(width))
        for a in range(0, len(rows), width)
    )
    return [(_TAG, v >> 8 & 255, v & 255) for v in values]


def _image(ops: list[_Op], read: int, offset: int, data: list[Pixel]) -> Raster:
    """Draw ``ops`` as a strip in row 1 and ``data`` in row 2 below the read.

    The start block is an L (so the IP at (0, 0) enters row 1); the final
    block is three tall.  The last op's block is lengthened so the image is
    wide enough that the final column's neighbours are black.
    """
    starts = [0, 2]
    for size, _ in ops[1:]:
        starts.append(starts[-1] + size)
    if data:
        column = starts[read + 1] + offset
        starts[-1] += max(0, column + len(data) + 2 - starts[-1] - 1)
    width = starts[-1] + 1
    rows = [[_BLACK] * width for _ in range(3)]
    colour = _START
    rows[0][0] = rows[1][0] = rows[1][1] = colour
    for index in range(1, len(ops)):
        colour = _next_colour(colour, ops[index - 1][1])
        for x in range(starts[index], starts[index + 1]):
            rows[1][x] = colour
    colour = _next_colour(colour, ops[-1][1])
    for row in rows:
        row[-1] = colour
    for x, pixel in enumerate(data, starts[read + 1] + offset if data else 0):
        rows[2][x] = pixel
    return Raster(tuple(tuple(row) for row in rows))


@cache
def _generate(truth_table: str, low: int | None = None) -> Raster:
    """Return the raster for ``low`` bit-position inputs, else the smallest."""
    inputs = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, inputs)
    if not essential:
        return _image(_constant(inputs, truth_table[0]), 0, 0, [])
    rows = read_at(truth_table, essential, inputs)
    if low is None:
        built = (_generate(truth_table, k) for k in range(2, _MOST_LOW + 1))
        return min(built, key=lambda r: len(r.rows[0]))
    low = min(low, len(essential))
    ops, read, offset = _program(inputs, essential, low)
    return _image(ops, read, offset, _pixels(rows, low))


def piet_plus_plus(truth_table: str) -> Raster:
    """Return a Piet++ raster computing ``truth_table``."""
    return _generate(truth_table)


LANGUAGE = Language(
    "Piet++",
    "piet_plus_plus",
    category="stack_based",
    # The slug rule drops "++" and would collide with Piet.
    id="piet_plus_plus",
    source_kind=SourceKind.RASTER,
    boolean=piet_plus_plus,
    no_wrap="a one-row strip with data beneath; layout fixes its own width",
    eof="an exhausted In command is ignored, as the page recommends",
)
