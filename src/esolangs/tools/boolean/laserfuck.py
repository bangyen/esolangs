"""The LaserFuck boolean generator.

One language, one file -- the pattern this package already follows for
``wii2d.py``, ``streetcode.py``, ``circuit_diagram.py``, and the rest of the
larger generators, and the one the text package follows for its own
LaserFuck.  It earns it here for the same reason: at ~420 lines it was
better than a quarter of ``other.py``, and it is the only generator in that
file that lays out a grid, builds a looping input reader, and rotates a
block on end to meet a width.
"""

from itertools import permutations
from typing import NamedTuple

from esolangs.tools import laserfuck_layout
from esolangs.tools.boolean.helpers import (
    _ORDER_SEARCH_MAX,
    _validate_truth_table,
    permute_truth_table,
)

__all__ = ["laserfuck"]


# The two loops that normalize the input cells.  ``,`` reads a character, so
# ``'0'``/``'1'`` arrive as 48/49 and every input needs 48 subtracted.
# Writing that straight costs 49 columns per input; running it as a loop
# costs a counter instead, and the counter itself is built by a second loop
# rather than by 48 ``+`` -- ``_LASER_OUTER * _LASER_INNER`` is 48.
_LASER_OUTER = 8
_LASER_INNER = 6


def _laserfuck_walk(frm: int, to: int) -> str:
    """Spell the tape walk from cell ``frm`` to cell ``to``."""
    return ">" * (to - frm) if to >= frm else "<" * (frm - to)


def _laserfuck_cells(n: int, perm: tuple[int, ...]) -> list[int]:
    """Return the cell each stream input is read into, indexed by input.

    A node is ``>#v)``: it steps the pointer and then tests the cell under
    it, so level ``k`` tests cell ``k + 1`` whatever is in it.  Level ``k``
    has to test original input ``perm[k]``, so that input is read into cell
    ``k + 1`` -- the *inverse* of ``perm``.  Reading it forward puts the
    right bits in the wrong cells and computes a different function.
    """
    cells = [0] * n
    for level, i in enumerate(perm):
        cells[i] = level + 1
    return cells


def _laserfuck_reads(n: int, perm: tuple[int, ...]) -> str:
    """Spell the reader's read section, placing the inputs in ``perm`` order.

    ``multiply`` ends on cell 1, so that is where the pointer starts; the
    section ends back on cell 0, the counter the second ring spends.  Under
    the identity order this is the plain ``,>,>,<<<`` the reader always
    emitted -- each read steps one cell on -- and a permuted order only
    changes the walks between the ``,``.

    Nothing here is conditional.  The read section sits between the two
    rings, past ``multiply``'s ``)`` and before ``retire``'s ``}``, so it is
    a straight run the beam crosses once: a walk cannot steer it, which
    frees the placement of the steering hazards a ring body would carry.
    """
    cells = _laserfuck_cells(n, perm)
    out = ""
    at = 1
    for cell in cells:
        out += _laserfuck_walk(at, cell) + ","
        at = cell
    return out + _laserfuck_walk(at, 0)


def _laserfuck_ring_reader(
    n: int, perm: tuple[int, ...] | None = None
) -> tuple[list[str], int]:
    r"""Build the looping input reader, and say how wide it is.

    Returns the reader's rows and the column the beam leaves them on, moving
    right, with the pointer on cell 0.

    The tape is laid out as *cell 0 = counter and answer*, cells 1..n =
    inputs.  Cell 0 earns that double duty: the counter ends the reader at
    zero and *touched*, which is exactly the state a ``0`` answer needs to
    print, so a leaf writes nothing for a zero and a single ``+`` for a one.

    Two loops run left to right, each a ring: a ``}`` faces the beam right
    along the body, ``#`` skips the deflector so ``)`` can test the cell
    under the pointer, and a nonzero cell turns the beam back to the ``/``,
    which drops it onto the return row where ``{`` sends it left to the
    ``^`` under the ring's own ``}``.  A zero cell lets the beam through the
    ``)`` and on to whatever follows on the row.

    The first ring multiplies: cell 1 is preloaded with ``_LASER_OUTER`` and
    each pass adds ``_LASER_INNER`` to cell 0, leaving the 48 the inputs
    need.  The reads then happen -- cell 1's preload is spent by now, so the
    inputs may use it -- and the second ring subtracts one from cell 0 and
    from every input per pass, running until the counter is spent.

    A ring body cannot be folded: the return leg re-enters at the ``}`` and
    re-runs the *whole* body, so a body split across rows would re-execute
    only its tail.  Both bodies therefore live on one row -- and when a
    width cannot hold that row, :func:`_laserfuck_rotate` stands the whole
    block on end rather than breaking it.
    """
    preload = ">" + "+" * _LASER_OUTER
    multiply = "<" + "+" * _LASER_INNER + ">" + "-#/)"
    # The reads land the inputs in cells 1..n and end back on the counter.
    # Which input goes in which cell is the reorder (see _laserfuck_reads).
    reads = _laserfuck_reads(n, tuple(range(n)) if perm is None else perm)
    # one '-' for the counter and one for each input, then home again
    retire = "".join("->" for _ in range(n)) + "-" + "<" * n + "#/)"

    body = "}" + preload + "}" + multiply + reads + "}" + retire
    top = [" "] * (len(body) + 2)
    ret = [" "] * (len(body) + 2)
    for i, char in enumerate(body):
        top[i] = char
    # each ring's return leg: '^' under its own '}', '{' under its '/'
    first = 1 + len(preload)
    ret[first] = "^"
    ret[first + 1 + multiply.index("/")] = "{"
    second = len(body) - len(retire) - 1
    ret[second] = "^"
    ret[second + 1 + retire.index("/")] = "{"
    return ["".join(top).rstrip(), "".join(ret).rstrip()], len(body)


# Rotating or mirroring a LaserFuck block is a character substitution: the
# ops are direction-agnostic and only the mirrors and heading-setters carry
# an orientation.  Rotating a quarter turn clockwise turns a rightward beam
# into a downward one, which is how a block too wide for a width is made
# tall instead.
_LASER_ROTATE = str.maketrans(
    {
        "/": "\\",
        "\\": "/",
        "_": "|",
        "|": "_",
        "(": ")",
        ")": "(",
        "{": "^",
        "}": "v",
        "^": "}",
        "v": "{",
    }
)


def _laserfuck_rotate(rows: list[str]) -> list[str]:
    r"""Turn ``rows`` a quarter turn, so a rightward block becomes downward.

    The cells move as any rotation moves them -- the last row becomes the
    first column -- and each is then substituted, since a mirror or a
    heading-setter means something different once the beam runs the other
    way.  ``,``, ``+``, ``-``, ``<``, ``>``, ``#`` and ``x`` are unchanged:
    they act on the tape, not on the beam.

    A reader is forty-odd columns and two rows laid flat; rotated it is two
    columns and forty-odd rows, which is what lets a narrow width still be
    met.
    """
    height = len(rows)
    width = max(len(line) for line in rows)
    padded = [line.ljust(width) for line in rows]
    return [
        "".join(padded[height - 1 - row][col] for row in range(height)).translate(
            _LASER_ROTATE
        )
        for col in range(width)
    ]


_LASER_FLIP_H = str.maketrans({"/": "\\", "\\": "/", "{": "}", "}": "{"})


def _laserfuck_flip(rows: list[str]) -> list[str]:
    r"""Mirror ``rows`` left to right, so a rightward block runs leftward.

    Like the rotation, this is a substitution: only the mirrors and the two
    horizontal heading-setters mean something different once the beam runs
    the other way, and the tape ops do not.  The rows are padded to a
    rectangle first, for the same reason -- a short row would mirror to a
    block whose cells no longer line up with the ones they pair with.
    """
    width = max(len(line) for line in rows)
    return [line.ljust(width)[::-1].translate(_LASER_FLIP_H) for line in rows]


def _laserfuck_reader_blocks(
    n: int,
    perm: tuple[int, ...] | None = None,
) -> list[list[str]]:
    """Cut the flat reader into rectangles, padded so a rotation is exact."""
    rows, _ = _laserfuck_ring_reader(n, perm)
    width = max(len(line) for line in rows)
    padded = [line.ljust(width) for line in rows]
    starts = [col for col, char in enumerate(padded[0]) if char == "}"]
    return [
        [
            line[start : starts[index + 1] if index + 1 < len(starts) else width]
            for line in padded
        ]
        for index, start in enumerate(starts)
    ]


class _LaserBlock(NamedTuple):
    """A reader ring placed in one of its two orientations.

    The beam always arrives travelling *right* and must leave travelling
    right, so a placement's whole contract is where it puts its cells and
    where it hands the beam back.  ``rows`` are the block's own cells, laid
    ``top`` rows below the origin; ``connectors`` are the extra
    ``(row, col, char)`` cells that steer the beam in and out; and
    ``exit_row``/``exit_col`` are the offsets to add to the origin to reach
    the cell the next block starts from.

    A flat block is the trivial case -- the beam runs straight along its
    single row, so it sits at the origin, needs no connectors, and hands
    the beam back on the same row past its right edge.  A rotated one is
    entered from above and left from below, which is why it sits one row
    down and carries the two connectors that turn the beam.
    """

    rows: list[str]
    top: int
    connectors: list[tuple[int, int, str]]
    exit_row: int
    exit_col: int


def _laserfuck_place(block: list[str], upright: str) -> _LaserBlock:
    r"""Give ``block`` an explicit entry/exit contract in one orientation.

    ``F`` leaves the block flat: the beam enters at its left edge and leaves
    on the same row past its right edge, so there is nothing to connect.
    ``R`` stands it on end with :func:`_laserfuck_rotate`, which turns the
    rightward beam downward -- so the placement needs a ``v`` one row
    *above* the block to drop the beam in at the rotated ring's own entry
    column, and a ``\`` one row *below* to turn it right again.  The entry
    column is read off the rotated block's first row rather than
    rediscovered by the caller.
    """
    if upright == "F":
        return _LaserBlock(block, 0, [], 0, len(block[0]))

    turned = _laserfuck_rotate(block)
    entry = turned[0].index("v")
    below = 1 + len(turned)
    # drop in from above, and turn right again once the beam is through
    connectors = [(0, entry, "v"), (below, entry, "\\")]
    return _LaserBlock(turned, 1, connectors, below, entry + 1)


def _laserfuck_placements(
    n: int,
    perm: tuple[int, ...] | None = None,
) -> list[dict[str, _LaserBlock]]:
    """Place every reader block in *both* orientations, once.

    The caller tries all ``2**count`` orientation words, and a block's
    placement depends only on the block and its own letter -- so cutting
    and rotating per word rebuilt the same ``2 * count`` placements
    ``2**count`` times.  Hoisting them here is what makes the order search
    affordable: at n=6 it turns 17 reader cuts and 16 rotations per
    candidate into one and two.
    """
    return [
        {upright: _laserfuck_place(block, upright) for upright in "FR"}
        for block in _laserfuck_reader_blocks(n, perm)
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

    # Render row by row from the cells that exist.  Probing every cell of
    # the bounding rectangle instead costs ``height x span`` dict lookups
    # for a grid that is mostly blank -- 5.8M of them on a six-input build,
    # the generator's hot path -- where the occupied cells are a small
    # fraction of that.  Bucketing by row and filling the gaps between the
    # columns actually present builds the same lines, ``rstrip`` included,
    # in time proportional to the marks rather than the area.
    height = max(r for r, _ in cells) + 1
    rows: list[list[tuple[int, str]]] = [[] for _ in range(height)]
    for (r, c), char in cells.items():
        rows[r].append((c, char))
    lines = []
    for marks in rows:
        marks.sort()
        parts: list[str] = []
        cursor = 0
        for c, char in marks:
            if c > cursor:
                parts.append(" " * (c - cursor))
            parts.append(char)
            cursor = c + 1
        lines.append("".join(parts))
    return lines, row, col


def _laserfuck_build(
    truth_table: str,
    perm: tuple[int, ...],
    width: int | None = None,
) -> str:
    r"""Build one LaserFuck program, reading its inputs in ``perm`` order.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame; ``perm`` is spent in exactly one place, the read section
    that decides which cell each input lands in.

    The laser starts at ``o`` with a random heading, so a mirror funnel
    (``|``/``^``/``_`` plus two ``}`` on the row above) sends every heading
    to the top row moving right.  There it meets the reader, then the tree.

    **The reader.**  ``,`` reads a character, so ``'0'``/``'1'`` arrive as
    48/49 and each input needs 48 subtracted.  Written straight that is 49
    columns per input; instead two rings do it as a loop
    (:func:`_laserfuck_ring_reader`).  The first multiplies 8 by 6 to build
    the 48, the second spends that counter one unit at a time across the
    counter and every input.  Each ring is a ``}`` facing the beam along
    its body, ``#`` skipping the deflector so ``)`` can test the cell under
    the pointer, and a return leg beneath.  The reader is two rows and a
    few dozen columns whatever ``n`` is.

    **The tape.**  The ring counter is cell 0 and the inputs are cells
    1..n.  That is not an accident of layout: the counter ends *touched at
    zero*, which is exactly what a zero answer must be for the dump to
    print it, so cell 0 doubles as the answer cell.

    **The tree.**  Each node writes ``>#v)``: the ``#`` skips the ``v`` on
    the way in, so ``)`` tests the cell under the pointer.  A zero passes
    straight through and the next node carries on *along the same row*;
    only a one turns the beam back onto the ``v``, which drops it to a
    ``\\`` that faces it right again on a fresh row.  Rows therefore scale
    with the number of *one* edges rather than with the node count, and the
    all-zeros path is a single straight line.  A leaf retires each input
    (driving the cell negative so the dump skips it), walks down to cell 0,
    and adds a ``+`` only if the answer is one -- a zero answer needs no
    code at all.

    A subtree whose rows all agree becomes a leaf rather than branching on
    bits that cannot change the answer, and how a leaf retires the inputs is
    what the fold turns on.  Sized to the bit, retiring is one ``-`` for a
    zero and two for a one -- but a folded leaf never learned the bits it
    did not branch on.  It does not have to: only the cells *above* its
    depth are unknown, and a flat two ``-`` retires either value (0 -> -2,
    1 -> -1), while the cells the path did consume keep the sized run.  So
    the flat form is spent exactly on the cells that need it, and a table
    with no constant subtree comes out as it did before folding.  The sweep
    still covers all ``n`` cells, since an unconsumed one sits at 0 or 1 and
    would print beside the answer, so a folded leaf steps out to cell ``n``
    first and sweeps back from there.

    LaserFuck has no output instruction: it prints the tape when the last
    laser dies, in decimal, skipping negative cells.  Cell (0, 0) is left
    blank deliberately -- a ``\\xff`` there would select byte mode.

    ``width`` bounds the columns.  The tree adds only a column or two past
    the reader, so the reader is what a width has to bargain with: laid flat
    it is one row and forty-odd columns, and when that will not fit
    :func:`_laserfuck_rotate` stands it on end instead -- two columns and
    forty-odd rows.  A ring body cannot be broken across rows, since the
    return leg re-enters at the ``}`` and re-runs the whole body, which is
    why the block is rotated rather than folded.  Below the width the *tree*
    needs there is nothing left to give, and the grid comes out as wide as
    the tree.
    """
    n = _validate_truth_table(truth_table)
    # The tree adds only a column or two past the reader, so the reader is
    # what a width has to bargain with: side by side the rings are one row
    # and forty-odd columns, stacked they are seven rows and under twenty.
    placements = _laserfuck_placements(n, perm)
    count = len(placements)
    candidates = []
    for choice in range(2**count):
        orientation = "".join("R" if choice >> b & 1 else "F" for b in range(count))
        rows_of, exit_row, exit_col = _laserfuck_assemble_reader(
            placements, orientation
        )
        span = max(len(line) for line in rows_of)
        candidates.append((len(rows_of), span, rows_of, exit_row, exit_col))
    candidates.sort(key=lambda item: (item[0], item[1]))
    fitting = [
        item
        for item in candidates
        if width is None or laserfuck_layout.MARGIN + item[1] + 2 <= width
    ]
    chosen = fitting[0] if fitting else min(candidates, key=lambda item: item[1])
    _, _, reader_rows, reader_exit_row, reader_exit_col = chosen

    margin = laserfuck_layout.MARGIN
    grid: list[list[str]] = []

    def put(row: int, col: int, char: str) -> None:
        """Write one cell, growing the ragged grid to reach it.

        The grid's final extent is not known here -- the tree is laid out
        and mirrored as it goes -- so it stays ragged and grows on demand.
        What changed is how: the two ``while`` loops appended one element
        per call, which is 1.8M calls and the generator's hot path on a
        six-input build.  Extending by the whole shortfall at once leaves
        the same grid and lets the list resize in one step.
        """
        if len(grid) <= row:
            grid.extend([] for _ in range(row + 1 - len(grid)))
        line = grid[row]
        # The layout fills each row left to right, so a column is never
        # already in range and this always extends.
        if len(line) <= col:  # pragma: no branch
            line.extend(" " * (col + 1 - len(line)))
        line[col] = char

    def put_run(row: int, col: int, text: str) -> None:
        """Write a whole run of cells, growing the ragged grid to reach it.

        The tree arrives as runs, and going through :func:`put` a character
        at a time is 1.7M calls on a six-input build once the order search
        multiplies it by ``n!``.  A slice assignment leaves the same line:
        the run is blank-free, so nothing it covers had to be preserved.
        """
        if len(grid) <= row:
            grid.extend([] for _ in range(row + 1 - len(grid)))
        line = grid[row]
        if len(line) < col:
            line.extend(" " * (col - len(line)))
        line[col : col + len(text)] = text

    # The funnel: every start heading ends up on row 0 moving right.  Cell
    # (0, 0) stays blank so the tape dumps in decimal rather than byte mode.
    put(0, 1, "}")
    put(0, 2, "}")
    put(1, 0, "|")
    put(1, 1, "o")
    put(1, 2, "^")
    put(2, 1, "_")

    # The rings go on rows 0 and 1; the beam leaves them still moving right
    # with the pointer on cell 0.
    for offset, text in enumerate(reader_rows):
        for index, char in enumerate(text):
            if char != " ":
                put(offset, margin + index, char)
    # The beam leaves the reader moving right, and turns down onto a row of
    # its own for the tree.  How far it has to fall depends on what the last
    # block left beneath it: a block laid flat keeps its ring's return leg
    # on the row below, which the beam must clear, while a rotated one ends
    # at its own foot with nothing under it.
    # The tree is built as a block of its own, then mirrored and hung under
    # the reader.  Laid out rightward it would have to be *reached*: the
    # beam leaves the reader at its far right, and a leftward return leg
    # would be needed to carry it back to the margin before the tree could
    # start.  Mirrored, the tree runs leftward from where the beam already
    # is, so that whole row disappears -- the beam simply turns down at the
    # reader's end and a '/' faces it into the tree.
    #
    # Within the tree a node writes ``>#v)``: the '#' skips the 'v' on the
    # way in, so ')' tests the cell under the pointer.  A zero passes
    # straight through and the next node continues on the same row; only a
    # one turns the beam back onto the 'v' and drops it, to a '\' that
    # faces it right again on a fresh row.  Rows therefore scale with the
    # number of *one* edges rather than with the node count, and the
    # all-zeros path is a single straight line.
    # The tree as ``(column, text)`` runs per row rather than a cell per
    # character.  Nothing it lays contains a blank -- the runs are built
    # from ``><-+`` and the rest are the literals ``x``, ``>#v)`` and
    # ``\`` -- and every row is filled strictly left to right, so a run is
    # the whole of what a cell dict was storing one character at a time.
    # The order search rebuilds this n! times, and the dict cost it twice:
    # 1.7M single-cell writes going in and 3.1M ``get`` probes coming back
    # out over the bounding rectangle, which is mostly blank because the
    # tree is a staircase.
    #
    # A row is appended exactly when a ``one`` edge creates it, and the
    # counter that names it is bumped in the same breath, so ``len(rows)``
    # is the next row index and the two stay in step.
    rows: list[list[tuple[int, str]]] = [[]]

    def emit(path: list[int], row: int, col: int) -> None:
        """Lay the subtree for ``path``, entered at ``(row, col)`` going right."""
        depth = len(path)
        first = int("".join(map(str, path)), 2) << (n - depth) if path else 0
        if depth == n or len(set(truth_table[first : first + 2 ** (n - depth)])) == 1:
            index = first
            # The rings leave the inputs in cells 1..n and cell 0 already
            # touched at zero, so the sweep walks down to it and a zero
            # answer needs no code at all.  The sweep must cover all ``n``
            # cells however deep the leaf is: an unconsumed one sits at 0 or
            # 1 and would print beside the answer.  The pointer is on cell
            # ``depth``, so step out to cell ``n`` before sweeping back.
            #
            # Cells above ``depth`` were never branched on, so their value is
            # unknown here and two ``-`` retire either one (0 -> -2, 1 ->
            # -1).  The cells the path *did* consume are known and keep the
            # sized run of one ``-`` more than the bit -- which is why a
            # table that folds nothing comes out exactly as it always did.
            run = ">" * (n - depth)
            run += "--<" * (n - depth)
            for level in range(depth, 0, -1):
                run += "-" * (path[level - 1] + 1) + "<"
            run += "+" if truth_table[index] == "1" else ""
            rows[row].append((col, run + "x"))
            return
        rows[row].append((col, ">#v)"))
        emit([*path, 0], row, col + 4)  # a zero carries on along this row
        drop = len(rows)
        rows.append([(col + 2, "\\")])  # a one comes down the 'v' column
        emit([*path, 1], drop, col + 3)

    emit([], 0, 0)
    span = max(col + len(text) for marks in rows for col, text in marks)
    upright = []
    for marks in rows:
        parts: list[str] = []
        cursor = 0
        for col, text in marks:
            if col > cursor:
                parts.append(" " * (col - cursor))
            parts.append(text)
            cursor = col + len(text)
        parts.append(" " * (span - cursor))
        upright.append("".join(parts))

    # Where the tree goes depends on whether the width can afford it.
    #
    # The beam leaves the reader still moving right, so the cheapest thing
    # is to carry straight on: the tree starts in the next column along, on
    # the reader's own rows, and costs no rows at all beyond the ones the
    # tree itself needs.  That only works if the grid may be as wide as the
    # reader and the tree laid end to end.
    #
    # Otherwise the tree is mirrored and hung underneath.  The beam turns
    # down at the reader's end and a '/' on the tree's first row faces it
    # left into a tree that runs backwards -- needing no row to be
    # *reached*, unlike a rightward tree below, which would need one to
    # carry the beam back to the margin first.
    straight = margin + reader_exit_col + max(len(line) for line in upright)
    if width is None or straight + 1 <= width:
        # Laid from the runs, not from the padded rows: the tree is a
        # staircase, so ``upright`` is mostly blanks, and a blank is
        # re-padded by the next run on its row (or ``rstrip``ed off the
        # end) rather than written.
        for offset, marks in enumerate(rows):
            for col, text in marks:
                put_run(reader_exit_row + offset, margin + reader_exit_col + col, text)
    else:
        flipped = _laserfuck_flip(upright)
        entry = len(flipped[0].rstrip()) - 1
        # A narrow reader can leave the beam further left than the tree is
        # wide, and the tree would run off the western edge.  Turning down
        # further to the right costs nothing but the blank cells it crosses,
        # so the fall column is pushed out to wherever the tree needs it.
        fall = max(margin + reader_exit_col, margin + entry + 1)
        # The tree hangs on the first row below the reader.  How far the beam
        # falls to reach it depends on what the last block left under the
        # exit -- a flat block keeps its ring's return leg one row down, a
        # rotated one ends at its own foot -- but the reader is sized to its
        # own last occupied row either way, so that clearance is just its
        # height, and the orientation does not have to be consulted at all.
        top = len(reader_rows)
        put(reader_exit_row, fall, "v")
        for offset, line in enumerate(flipped):
            for index, char in enumerate(line):
                put(top + offset, fall - 1 - entry + index, char)
        put(top, fall, "/")

    lines = ["".join(line).rstrip() for line in grid]
    while lines and not lines[-1]:
        lines.pop()  # pragma: no cover - the grid ends on content
    return "\n".join(lines)


def laserfuck(truth_table: str, width: int | None = None) -> str:
    """Build a LaserFuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    :func:`_laserfuck_build` is the construction and its docstring is the
    account of it; this is the search over input orders around it.

    The tree splits on its inputs in whichever order emits the shortest
    program, so more subtrees fold.  That is a *placement*: a node is
    ``>#v)``, which steps the pointer and tests the cell under it, so level
    ``k`` tests cell ``k + 1`` whatever is in it, and moving which cell an
    input is read into changes what every node tests.  Only the reader's
    read section changes (see :func:`_laserfuck_reads`); the tree, the fold,
    the leaf sweeps and the retire ring are untouched, and the reads stay in
    stream order -- one ``,`` per input, left to right.

    The identity order is built first and ties keep it, so a table no
    reorder improves emits exactly what it emitted before.

    A width is applied to every candidate rather than to the winner: the
    reader's orientations and the tree's placement already trade rows
    against columns, so the narrowest program is often not the shortest,
    and the choice has to be made over the whole pool.
    """
    n = _validate_truth_table(truth_table)
    identity = tuple(range(n))
    orders = [identity]
    if n <= _ORDER_SEARCH_MAX:
        orders += [p for p in permutations(range(n)) if p != identity]

    best = _laserfuck_build(truth_table, identity, width)
    for perm in orders[1:]:
        candidate = _laserfuck_build(
            permute_truth_table(truth_table, perm), perm, width
        )
        if len(candidate) < len(best):
            best = candidate
    return best
