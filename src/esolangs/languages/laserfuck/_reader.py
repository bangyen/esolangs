"""Build Laserfuck input rings and locate the outgoing beam."""

from functools import cache
from typing import NamedTuple

from esolangs.generation.helpers import move_text
from esolangs.languages.laserfuck._layout import (
    MARGIN,
    _laserfuck_join,
    _laserfuck_rotate,
)

# The two loops that normalize the input cells.  ``,`` reads a character, so
# ``'0'``/``'1'`` arrive as 48/49 and every input needs 48 subtracted.
# Writing that straight costs 49 columns per input; running it as a loop
# costs a counter instead, and the counter itself is built by a second loop
# rather than by 48 ``+``.
_LASER_OUTER = 8
_LASER_INNER = 6
_LASER_BIAS = _LASER_OUTER * _LASER_INNER  # 48, the code of '0'


def _laserfuck_reads(n: int) -> str:
    """Spell the reader's read section, placing the inputs in stream order.

    ``multiply`` ends on cell 1, where the pointer starts; the section ends
    on cell 0, the counter the second ring spends.  Stream order is the
    plain ``,>,>,<<<`` (each read steps one cell on, so input ``k`` lands
    in cell ``k + 1``).

    Nothing here is conditional: the section sits between the two rings, past
    ``multiply``'s ``)`` and before ``retire``'s ``}``, a straight run the
    beam crosses once.  A walk cannot steer it, which frees the placement of
    the steering hazards a ring body would carry.
    """
    # A node ``>#v)`` steps the pointer, then tests: level k tests cell k + 1.
    out = ""
    at = 1
    for cell in range(1, n + 1):
        out += move_text(at, cell, ">", "<") + ","
        at = cell
    return out + move_text(at, 0, ">", "<")


def _laserfuck_ring_reader(n: int) -> list[str]:
    r"""Build the looping input reader.

    Returns the reader's rows; the beam leaves them moving right, with the
    pointer on cell 0.

    The tape is *cell 0 = counter and answer*, cells 1..n = inputs.  The
    counter ends the reader at zero and *touched*, the state a ``0`` answer
    needs to print, so a leaf writes nothing for a zero and a single ``+``
    for a one.

    Two loops run left to right, each a ring: a ``}`` faces the beam right
    along the body, ``#`` skips the deflector so ``)`` can test the cell
    under the pointer, and a nonzero cell turns the beam back to the ``/``,
    which drops it onto the return row where ``{`` sends it left to the
    ``^`` under the ring's own ``}``.  A zero cell lets the beam through the
    ``)`` and on along the row.

    The first ring multiplies: cell 1 is preloaded with ``_LASER_OUTER`` and
    each pass adds ``_LASER_INNER`` to cell 0, leaving the 48 the inputs
    need.  The reads then happen (cell 1's preload is spent, so inputs may
    use it); the second ring subtracts one from cell 0 and from every input
    per pass, until the counter is spent.

    A ring body cannot be folded: the return leg re-enters at the ``}`` and
    re-runs the *whole* body, so a body split across rows would re-execute
    only its tail.  Both bodies live on one row; when a width cannot hold
    it, :func:`_laserfuck_rotate` stands the whole block on end.
    """
    preload = ">" + "+" * _LASER_OUTER
    multiply = "<" + "+" * _LASER_INNER + ">" + "-#/)"
    # The reads land the inputs in cells 1..n, in stream order, and end
    # back on the counter (see _laserfuck_reads).
    reads = _laserfuck_reads(n)
    # one '-' for the counter and one for each input, then home again
    retire = "->" * n + "-" + "<" * n + "#/)"

    body = "}" + preload + "}" + multiply + reads + "}" + retire
    top = [*body, " ", " "]
    ret = [" "] * (len(body) + 2)
    # each ring's return leg: '^' under its own '}', '{' under its '/'
    first = 1 + len(preload)
    ret[first] = "^"
    ret[first + 1 + multiply.index("/")] = "{"
    second = len(body) - len(retire) - 1
    ret[second] = "^"
    ret[second + 1 + retire.index("/")] = "{"
    return ["".join(top).rstrip(), "".join(ret).rstrip()]


def _laserfuck_reader_blocks(n: int) -> list[list[str]]:
    """Cut the flat reader into rectangles, padded so a rotation is exact."""
    rows = _laserfuck_ring_reader(n)
    width = max(len(line) for line in rows)
    padded = [line.ljust(width) for line in rows]
    starts = [col for col, char in enumerate(padded[0]) if char == "}"]
    return [
        [line[start:stop] for line in padded]
        for start, stop in zip(starts, [*starts[1:], width], strict=True)
    ]


class _LaserBlock(NamedTuple):
    """A reader ring placed in one of its two orientations.

    The beam arrives and leaves travelling *right*.  ``rows`` are the
    block's cells, laid ``top`` rows below the origin; ``connectors`` are
    extra ``(row, col, char)`` cells steering the beam in and out;
    ``exit_row``/``exit_col`` are origin offsets to the cell the next block
    starts from.  A flat block needs no connectors; a rotated one is entered
    from above and left from below, so it sits one row down with two.
    """

    rows: list[str]
    top: int
    connectors: list[tuple[int, int, str]]
    exit_row: int
    exit_col: int


def _laserfuck_place(block: list[str], upright: str) -> _LaserBlock:
    r"""Give ``block`` an explicit entry/exit contract in one orientation.

    ``F`` leaves the block flat.  ``R`` stands it on end with
    :func:`_laserfuck_rotate`, so the beam needs a ``v`` one row *above* to
    drop in at the rotated ring's entry column (read off its first row) and
    a ``\`` one row *below* to turn right again.
    """
    if upright == "F":
        return _LaserBlock(block, 0, [], 0, len(block[0]))

    turned = _laserfuck_rotate(block)
    entry = turned[0].index("v")
    below = 1 + len(turned)
    # drop in from above, and turn right again once the beam is through
    connectors = [(0, entry, "v"), (below, entry, "\\")]
    return _LaserBlock(turned, 1, connectors, below, entry + 1)


def _laserfuck_placements(n: int) -> list[dict[str, _LaserBlock]]:
    """Place every reader block in *both* orientations, once.

    The caller tries all ``2**count`` orientation words, and a block's
    placement depends only on the block and its own letter -- so cutting
    and rotating per word rebuilt the same ``2 * count`` placements
    ``2**count`` times.  Hoisting them turns 17 reader cuts and 16 rotations
    at n=6 into one and two per candidate.
    """
    return [
        {upright: _laserfuck_place(block, upright) for upright in "FR"}
        for block in _laserfuck_reader_blocks(n)
    ]


def _laserfuck_assemble_reader(
    placements: list[dict[str, _LaserBlock]],
    orientation: str,
) -> tuple[list[str], int, int]:
    """Chain the reader's blocks, each flat (``F``) or on end (``R``).

    Each block is placed by :func:`_laserfuck_place`, which declares where
    the beam enters and leaves it; this function only walks that contract,
    laying each block at the cell the previous one handed the beam to.
    """
    cells: dict[tuple[int, int], str] = {}

    def put(row: int, col: int, char: str) -> None:
        if char != " ":
            cells[(row, col)] = char

    row = col = 0
    for choices, upright in zip(placements, orientation, strict=True):
        placed = choices[upright]
        for offset, line in enumerate(placed.rows):
            for index, char in enumerate(line):
                put(row + placed.top + offset, col + index, char)
        for offset, index, char in placed.connectors:
            put(row + offset, col + index, char)
        row += placed.exit_row
        col += placed.exit_col

    # Bucket by row and fill gaps rather than probing the bounding
    # rectangle: a six-input build's eight reader rectangles total 6,644
    # cells (2026-10-21; 5.8M under an earlier, mostly-blank layout).
    height = max(r for r, _ in cells) + 1
    rows: list[list[tuple[int, str]]] = [[] for _ in range(height)]
    for (r, c), char in cells.items():
        rows[r].append((c, char))
    return [_laserfuck_join(sorted(marks)) for marks in rows], row, col


class _LaserReader(NamedTuple):
    rows: tuple[str, ...]
    exit_row: int
    exit_col: int


class _ReaderCandidate(NamedTuple):
    height: int
    span: int
    reader: _LaserReader


@cache
def _laserfuck_reader_candidates(n: int) -> tuple[_ReaderCandidate, ...]:
    """Every orientation word's reader, shortest first (height, then span).

    The search depends on ``n`` alone -- a truth table never
    reaches the reader, and a width only *filters* the result -- so every
    build at one arity rebuilt the same ``2**count`` readers.
    Caching it hoists the search out of the per-build path the way
    :func:`_laserfuck_placements` hoisted the cuts out of the per-word one.
    Rows come back as tuples because the callers only read them.
    """
    placements = _laserfuck_placements(n)
    count = len(placements)
    candidates = []
    for choice in range(2**count):
        orientation = "".join("R" if choice >> b & 1 else "F" for b in range(count))
        rows_of, exit_row, exit_col = _laserfuck_assemble_reader(
            placements, orientation
        )
        span = max(len(line) for line in rows_of)
        reader = _LaserReader(tuple(rows_of), exit_row, exit_col)
        candidates.append(_ReaderCandidate(len(rows_of), span, reader))
    # Stable, so ties still break on the orientation word's own order.
    candidates.sort(key=lambda item: (item.height, item.span))
    return tuple(candidates)


def _laserfuck_reader(
    n: int, width: int | None, *, vertical_tree: bool
) -> _LaserReader:
    """Select the reader placement and its outgoing beam position."""
    # The tree adds only a column or two past the reader, so the reader is
    # what a width has to bargain with: side by side the rings are one row
    # and forty-odd columns, stacked they are seven rows and under twenty.
    if vertical_tree:
        placements = _laserfuck_placements(n)
        rows, exit_row, exit_col = _laserfuck_assemble_reader(
            placements, "R" * len(placements)
        )
        return _LaserReader(tuple(rows), exit_row, exit_col)
    candidates = _laserfuck_reader_candidates(n)
    fitting = [
        item for item in candidates if width is None or MARGIN + item.span + 2 <= width
    ]
    chosen = fitting[0] if fitting else min(candidates, key=lambda item: item.span)
    return chosen.reader
