"""LaserFuck Boolean program generator: a reader ring, then a decision tree.

The reader normalizes the input characters into cells 1..n; the tree tests
them with ``>#v)`` nodes, one row per *one* edge, and each leaf retires the
cells and adds ``+`` for a one.  Subtrees that agree become leaves, but equal
subtrees are never shared.  Input order stays the identity (see
:func:`_laserfuck_pool`).  Above sixty-four entries (without a width)
the weighted linear-space lookup replaces the tree.

Size:
    About 23T chars from n=7 (weighted lookup); the tree under it:
    n=4 random 1847: 548 chars, n=5 random 1847: 1,640 chars,
    n=6 random 1847: 4,241 chars, n=10 random 1847: 24,605 chars,
    n=16 and: 1,443,471 chars.

Decisions:
    The narrowest-reader (width=1) layout is 13.1% shorter by length at n=4
    (random 1847) but triples the area (-225.9%), so it is not tried.  A
    greedy input order did not pay (measured in :func:`_laserfuck_pool`), so
    the identity order is built instead.
"""

from functools import cache
from itertools import zip_longest
from typing import NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    grid_area,
    grid_width,
    input_weights,
    move_text,
    narrowest_grid,
    subtree_ids,
)
from esolangs.languages.laserfuck.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

__all__ = ["laserfuck"]

# The leftmost column code may use.  Columns 0..2 carry the funnel (``|o^``
# and the ``_`` beneath it), which every initial heading is routed through
# at startup, so code there would drop the beam back onto the funnel and
# start the program over.
MARGIN = 3


# The two loops that normalize the input cells.  ``,`` reads a character, so
# ``'0'``/``'1'`` arrive as 48/49 and every input needs 48 subtracted.
# Writing that straight costs 49 columns per input; running it as a loop
# costs a counter instead, and the counter itself is built by a second loop
# rather than by 48 ``+``.
_LASER_OUTER = 8
_LASER_INNER = 6
_LASER_BIAS = _LASER_OUTER * _LASER_INNER  # 48, the code of '0'


def _laserfuck_weighted(truth_table: str) -> str:
    r"""Build the table in linear space with weighted conditional walks.

    The top row first writes the T answer cells one band to the right, then
    returns to cell zero.  Input bit ``i`` conditionally crosses an arm of
    ``T/2**(i+1)`` ``>`` commands; the arm lengths sum to ``T-1``, so the
    pointer finishes at its binary input index.  A fixed T-step walk reaches
    that answer cell and adds two.

    Moving left 2T steps deliberately overruns the tape.  Prepending cells
    shifts the chosen answer to cell 2T regardless of its index.  One 3T-cell
    sweep subtracts two everywhere: every other initialized answer and every
    input becomes negative, while the chosen cell becomes exactly its table
    bit.  LaserFuck prints only touched nonnegative cells, hence only it.

    A conditional arm is a two-row diamond.  ``#v)`` lets zero continue on
    the top row; one reflects onto ``v``, crosses the lower arm, and rises to
    the same ``}`` exit.  The three rows, table initialization, arms, and
    cleanup all have total length O(T), and construction performs only those
    linear appends.  An ignored input is read and normalized but crosses no
    arm, so T counts the essential inputs alone.
    """
    weights, truth_table = input_weights(
        truth_table, _validate_truth_table(truth_table)
    )
    size = len(truth_table)
    top = list(" }}}")
    middle = list("|o^ ")
    bottom = list(" _  ")

    def straight(text: str) -> None:
        top.extend(text)
        middle.extend(" " * len(text))
        bottom.extend(" " * len(text))

    straight(">" * size)
    straight("".join(("+" if bit == "1" else "") + ">" for bit in truth_table))
    straight("<" * (2 * size))
    for arm in weights:
        straight("," + "-" * _LASER_BIAS)
        if not arm:
            continue
        upper = "#v)" + " " * (arm - 1) + "}"
        lower = " }" + ">" * arm + "^"
        top.extend(upper)
        middle.extend(lower)
        bottom.extend(" " * len(upper))
    straight(">" * size + "++" + "<" * (2 * size) + "-->" * (3 * size) + "x")
    return "\n".join("".join(row).rstrip() for row in (top, middle, bottom))


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

    Cells move as in any rotation (the last row becomes the first column)
    and are then substituted, since a mirror or heading-setter means
    something different once the beam runs the other way.  ``,``, ``+``,
    ``-``, ``<``, ``>``, ``#`` and ``x`` are unchanged: they act on the tape,
    not the beam.

    A reader laid flat is forty-odd columns by two rows; rotated, two columns
    by forty-odd rows, which meets a narrow width.
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


def _laserfuck_join(marks: list[tuple[int, str]]) -> str:
    """Join ``(column, text)`` runs left to right, padding gaps with blanks."""
    parts: list[str] = []
    cursor = 0
    for col, text in marks:
        parts.append(" " * (col - cursor) + text)
        cursor = col + len(text)
    return "".join(parts)


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


class _LaserTree(NamedTuple):
    runs: list[list[tuple[int, str]]]
    upright: list[str]


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


class _LaserGrid:
    def __init__(self) -> None:
        self.cells: list[list[str]] = []

    def _row(self, row: int) -> list[str]:
        if len(self.cells) <= row:
            self.cells.extend([] for _ in range(row + 1 - len(self.cells)))
        return self.cells[row]

    def put(self, row: int, col: int, char: str) -> None:
        """Write one cell, growing the ragged grid to reach it.

        Extends by the whole shortfall at once: per-element appends were
        1.8M calls, the hot path of a six-input build.
        """
        line = self._row(row)
        # The layout fills each row left to right, so a column is never
        # already in range and this always extends.
        if len(line) <= col:  # pragma: no branch
            line.extend(" " * (col + 1 - len(line)))
        line[col] = char

    def put_run(self, row: int, col: int, text: str) -> None:
        """Write a whole run of cells, growing the ragged grid to reach it.

        Going through :meth:`put` a character at a time dominated six-input
        builds; the run is blank-free, so a slice assignment loses nothing.
        """
        line = self._row(row)
        if len(line) < col:
            line.extend(" " * (col - len(line)))
        line[col : col + len(text)] = text

    def render(self) -> str:
        lines = ["".join(line).rstrip() for line in self.cells]
        while lines and not lines[-1]:
            lines.pop()  # pragma: no cover - the grid ends on content
        return "\n".join(lines)


class _TreeEmitter:
    r"""Lays the decision tree as ``(column, text)`` runs, one row per *one* edge.

    The tree is built as its own block, mirrored, and hung under the reader:
    the beam turns down at the reader's end and a ``/`` faces it left, so no
    return row is needed to reach a rightward tree.  A node is ``>#v)``: ``#``
    skips the ``v`` going in, ``)`` tests the cell; a zero continues on the
    row, a one turns back onto ``v`` and drops to a ``\`` on a fresh row.
    Rows are blank-free runs (``><-+``, ``x``, ``>#v)``, ``\``) filled left to
    right.  A row is appended exactly when a ``one`` edge creates it, so
    ``len(rows)`` is the next index.
    """

    def __init__(self, truth_table: str, n: int) -> None:
        self.table = truth_table
        self.n = n
        self.ids = subtree_ids(truth_table)
        self.rows: list[list[tuple[int, str]]] = [[]]

    def leaf(
        self, depth: int, first: int, row: int, col: int, skipped: int = 0
    ) -> None:
        """Sweep the cells, then ``+`` for a one answer and ``x``.

        Inputs sit in cells 1..n, cell 0 at zero, so a zero answer needs no
        code.  Sweep all ``n`` cells from cell ``n`` down or an unconsumed one
        prints beside the answer.  A cell the path consumed (bit ``b``) takes
        ``-`` x ``b + 1``; one with no test (``skipped`` bit set: an equal-
        halves step, or a level past ``depth``) takes a flat two ``-``, which
        retires either value.  See [ablations.sized_leaf_retirement]: the
        balanced route uses this tree at every n, 17-21% area on random
        tables at n=10..12, 18-19% on parity (seeds 1, 7).
        """
        n = self.n
        run = ">" * (n - depth) + "--<" * (n - depth)
        for level in range(depth, 0, -1):
            bit = (first >> (n - level)) & 1
            run += "-" * (2 if skipped >> (level - 1) & 1 else bit + 1) + "<"
        run += "+" if self.table[first] == "1" else ""
        self.rows[row].append((col, run + "x"))

    def emit(
        self, depth: int, first: int, row: int, col: int, skipped: int = 0
    ) -> None:
        """Lay one row span, entered at ``(row, col)`` going right."""
        n = self.n
        if depth == n:
            self.leaf(depth, first, row, col, skipped)
            return
        below = self.ids[depth + 1]
        place = first >> (n - depth)
        if below[2 * place] == below[2 * place + 1]:
            # Equal halves (an ignored input, a repeat): the input is still
            # read, so step the pointer past its cell, but test nothing.
            self.rows[row].append((col, ">"))
            self.emit(depth + 1, first, row, col + 1, skipped | 1 << depth)
            return
        self.rows[row].append((col, ">#v)"))
        self.emit(depth + 1, first, row, col + 4, skipped)  # zero carries on
        drop = len(self.rows)
        self.rows.append([(col + 2, "\\")])  # a one comes down the 'v' column
        self.emit(depth + 1, first + 2 ** (n - depth - 1), drop, col + 3, skipped)


def _laserfuck_tree(truth_table: str, n: int) -> _LaserTree:
    """Emit the decision-tree runs and their padded upright block."""
    tree = _TreeEmitter(truth_table, n)
    tree.emit(0, 0, 0, 0)
    rows = tree.rows
    span = max(col + len(text) for marks in rows for col, text in marks)
    upright = [_laserfuck_join(marks).ljust(span) for marks in rows]
    return _LaserTree(rows, upright)


def _laserfuck_attach_tree(
    grid: _LaserGrid,
    reader: _LaserReader,
    tree: _LaserTree,
    width: int | None,
    *,
    vertical_tree: bool,
) -> None:
    """Place the tree straight, rotated, or hanging beneath its reader."""
    margin = MARGIN
    reader_rows, reader_exit_row, reader_exit_col = reader
    rows, upright = tree
    # Carry straight on into the tree if the width allows reader + tree
    # end to end; otherwise mirror it and hang it underneath (a '/' faces
    # the beam left, so no return row is needed).
    straight_width = margin + reader_exit_col + max(len(line) for line in upright)
    if vertical_tree:
        turned = _laserfuck_rotate(upright)
        entry = margin + len(upright) - 1
        exit_col = margin + reader_exit_col
        top = len(reader_rows)
        if entry < exit_col:
            grid.put(reader_exit_row, exit_col, "v")
            grid.put(top, exit_col, "/")
            grid.put(top, entry, "v")
            top += 1
        else:
            grid.put(reader_exit_row, entry, "v")
        for offset, line in enumerate(turned):
            for index, char in enumerate(line):
                grid.put(top + offset, margin + index, char)
    elif width is None or straight_width + 1 <= width:
        # Laid from the runs, not from the padded rows: the tree is a
        # staircase, so ``upright`` is mostly blanks, and a blank is
        # re-padded by the next run on its row (or ``rstrip``ed off the
        # end) rather than written.
        for offset, marks in enumerate(rows):
            for col, text in marks:
                grid.put_run(
                    reader_exit_row + offset, margin + reader_exit_col + col, text
                )
    else:
        flipped = _laserfuck_flip(upright)
        entry = len(flipped[0].rstrip()) - 1
        # A narrow reader can leave the beam further left than the tree is
        # wide, and the tree would run off the western edge.  Turning down
        # further to the right costs nothing but the blank cells it crosses,
        # so the fall column is pushed out to wherever the tree needs it.
        fall = max(margin + reader_exit_col, margin + entry + 1)
        # The reader is sized to its last occupied row (a flat block's
        # return leg or a rotated block's foot), so clearance is its height.
        top = len(reader_rows)
        grid.put(reader_exit_row, fall, "v")
        for offset, line in enumerate(flipped):
            for index, char in enumerate(line):
                grid.put(top + offset, fall - 1 - entry + index, char)
        grid.put(top, fall, "/")


def _laserfuck_build(
    truth_table: str,
    width: int | None = None,
    *,
    vertical_tree: bool = False,
) -> str:
    r"""Build one LaserFuck program, placing inputs in stream order.

    The laser starts at ``o`` with a random heading, so a mirror funnel
    (``|``/``^``/``_`` plus two ``}`` on the row above) sends every heading
    to the top row moving right, into the reader and then the tree (see
    :func:`_laserfuck_ring_reader`, :func:`_laserfuck_tree`).  Rows scale
    with the number of *one* edges, and the all-zeros path is one line.

    A subtree whose rows all agree becomes a leaf.  A flat two ``-``
    retires either value (0 -> -2, 1 -> -1), and the sweep covers all
    ``n`` cells, since an unconsumed one sits at 0 or 1 and would print
    beside the answer.

    LaserFuck prints the tape when the last laser dies, in decimal, skipping
    negative cells.  Cell (0, 0) is left blank deliberately -- a ``\\xff``
    there would select byte mode.

    ``width`` bounds the columns.  When the flat reader will not fit,
    :func:`_laserfuck_rotate` stands it on end; below the width the *tree*
    needs, the grid comes out as wide as the tree.

    Under a width, the admitted readers are all built, plus the upright
    placement the pool keeps for at most eight entries, and the
    least-area program that fits wins.  Ranking readers by their own
    (height, span) box instead picks wider programs, because a reader's
    height adds to the program's while its span often does not (the
    width-path picks cost 16.0% of area at n=3 against the flat reader,
    measured in the 2026-10-18 area re-audit); ranking by the box
    itself is worse still (+38% of area when raced naively).  Most of
    that cost is the upright placement never being raced when the
    first build already fits, so it is a candidate here.  When no
    candidate fits, the first admitted reader's build is returned, so
    the pool's fallbacks see exactly today's build.  Ties keep the
    (height, span) order of :func:`_laserfuck_reader_candidates`, the
    upright placement last.
    """
    n = _validate_truth_table(truth_table)
    tree = _laserfuck_tree(truth_table, n)
    if width is None or vertical_tree:
        reader = _laserfuck_reader(n, width, vertical_tree=vertical_tree)
        return _laserfuck_assemble(reader, tree, width, vertical_tree=vertical_tree)
    candidates = _laserfuck_reader_candidates(n)
    fitting = [item for item in candidates if MARGIN + item.span + 2 <= width]
    if not fitting:
        fallback = min(candidates, key=lambda item: item.span)
        return _laserfuck_assemble(fallback.reader, tree, width)
    builds = [_laserfuck_assemble(item.reader, tree, width) for item in fitting]
    if len(truth_table) <= 8:
        upright = _laserfuck_reader(n, width, vertical_tree=True)
        builds.append(_laserfuck_assemble(upright, tree, width, vertical_tree=True))
    fits = [program for program in builds if grid_width(program) <= width]
    return min(fits, key=grid_area) if fits else builds[0]


def _laserfuck_assemble(
    reader: _LaserReader,
    tree: _LaserTree,
    width: int | None,
    *,
    vertical_tree: bool = False,
) -> str:
    """Place one reader and the tree on a grid and render the program."""
    grid = _LaserGrid()
    _laserfuck_funnel(grid)
    # The rings go on rows 0 and 1; the beam leaves them still moving right
    # with the pointer on cell 0.
    for offset, text in enumerate(reader.rows):
        for index, char in enumerate(text):
            if char != " ":
                grid.put(offset, MARGIN + index, char)
    _laserfuck_attach_tree(grid, reader, tree, width, vertical_tree=vertical_tree)
    return grid.render()


_FUNNEL = ((0, 1, "}"), (0, 2, "}"), (1, 0, "|"), (1, 1, "o"), (1, 2, "^"), (2, 1, "_"))


def _laserfuck_funnel(grid: _LaserGrid) -> None:
    """Draw the start funnel: every heading ends up on row 0 moving right.

    Cell (0, 0) stays blank so the tape dumps in decimal rather than byte mode.
    """
    for row, col, char in _FUNNEL:
        grid.put(row, col, char)


def laserfuck(truth_table: str, width: int | None = None) -> str:
    """Build a LaserFuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    :func:`_laserfuck_build` is the construction; this is the race over
    tree placements around it (:func:`_laserfuck_pool`).  A width is applied to
    every candidate, not the winner: the reader's orientations and the tree's
    placement already trade rows against columns, so the narrowest program is
    often not the shortest.
    """
    _validate_truth_table(truth_table)
    if width is None and len(truth_table) > 64:
        return _laserfuck_weighted(truth_table)
    return _laserfuck_pool(truth_table, width)


def _laserfuck_pool(truth_table: str, width: int | None) -> str:
    """Return the best candidate over tree placements.

    Input order stays the identity: a node is ``>#v)``, which steps the pointer
    and tests the cell under it, so a reorder changes what every node tests; a
    greedy order saved 0% at n=6..8 (40 random tables) and at most 4.3% at n<=4.
    """
    _validate_truth_table(truth_table)
    best = _laserfuck_build(truth_table, width)
    if width is not None and grid_width(best) > width:
        # Move the start funnel above the computation, reclaiming its three
        # reserved columns. Two '/' turns enter its first heading setter.
        best = _laserfuck_raise_funnel(best)
        # Turning the staircase upright costs O(T log T) padding in general;
        # this bounded fallback keeps the full family O(T).
        if grid_width(best) > width and len(truth_table) <= 8:
            candidate = _laserfuck_build(truth_table, width, vertical_tree=True)
            if grid_width(candidate) > width:
                candidate = _laserfuck_raise_funnel(candidate)
            best = narrowest_grid(best, candidate)
    if width is not None and len(truth_table) <= 4 and grid_width(best) > max(width, 4):
        return _laserfuck_four_columns(truth_table)
    return best


def _laserfuck_four_columns(table: str) -> str:
    """Return a four-column vertical reader and tree for at most two inputs."""
    n = _validate_truth_table(table)
    cells: dict[tuple[int, int], str] = {}

    def vertical(row: int, col: int, text: str) -> int:
        for offset, char in enumerate(text):
            cells[row + offset, col] = char
        return row + len(text)

    # The original heading funnel enters a separate vertical read column.
    for row, col, char in (*_FUNNEL, (0, 3, "v"), (3, 3, "{"), (3, 2, "v")):
        cells[row, col] = char
    end = vertical(4, 2, (">," + "-" * _LASER_BIAS) * n + "<" * n)

    def select(row: int, one_column: int) -> int:
        vertical(row, 2, ">#" + ("}" if one_column == 3 else "{") + "(")
        cells[row + 2, one_column] = "v"
        return row + 4

    def leaves(row: int, base: int) -> int:
        first = select(row, 3)
        ends = []
        for bit, col in enumerate((2, 3)):
            index = base + bit
            bits = format(index, f"0{n}b")
            cleanup = "".join("-" * (int(value) + 1) + "<" for value in bits[::-1])
            # Touch cell zero even when its answer is zero; retire input cells.
            cleanup += "+" * (table[index] == "1") + "+-x"
            ends.append(vertical(first, col, cleanup))
        return max(ends)

    if n == 1:
        leaves(end, 0)
    else:
        zero = select(end, 1)
        stop = leaves(zero, 0)
        # The root's one arm bypasses both zero-arm leaves in column one.
        cells[stop + 1, 1] = "}"
        cells[stop + 1, 2] = "v"
        leaves(stop + 2, 2)
    return "\n".join(
        "".join(cells.get((row, col), " ") for col in range(4)).rstrip()
        for row in range(max(row for row, _ in cells) + 1)
    )


def _laserfuck_raise_funnel(program: str) -> str:
    """Move startup above the computation, reclaiming its three reserved columns."""
    rows = program.splitlines()
    shifted = [line[MARGIN:] for line in rows]
    entry = len(shifted[0]) - len(shifted[0].lstrip())
    route = " " * entry + "/" + " " * (2 - entry) + "/"
    return "\n".join([" }}v", "|o^", " _", route, *shifted])


def balance_laserfuck(table: str, default: str) -> str:
    """Compare reader fits, tree placements and startup-funnel fits."""
    n = _validate_truth_table(table)
    margin = MARGIN
    events = {1, 4}
    span = max(map(len, _laserfuck_tree(table, n).upright))
    for candidate in _laserfuck_reader_candidates(n):
        exit_column = candidate.reader.exit_col
        events.update((margin + candidate.span + 2, margin + exit_column + span + 1))
    boundaries = sorted(events)
    widths = set(boundaries)
    for start, stop in zip_longest(boundaries, boundaries[1:]):
        form = _laserfuck_build(table, start)
        # Reader and tree geometry is fixed within this interval. Only the
        # source's own fit can switch its startup funnel or narrow fallback.
        spans = {grid_width(form), grid_width(_laserfuck_raise_funnel(form))}
        widths.update(
            span for span in spans if start < span and (stop is None or span < stop)
        )
    # Local: a module-level import changes the dump's callable keys.
    from esolangs.generation.wrap import balance_score

    return min(
        default,
        *(laserfuck(table, width) for width in sorted(widths)),
        key=balance_score,
    )


LANGUAGE = Language(
    "LaserFuck",
    "laserfuck",
    category="grid_based",
    random=True,
    boolean=laserfuck,
    split=True,
    contract=BooleanContract(
        answer_mode="dump",
        note="the initial heading is random by spec, so the example pins "
        "the source it is drawn from: seed 0 draws heading 3",
        input_shape="char_stream",
    ),
    balance=balance_laserfuck,
    proof_execution=(execution, True, (5, 6, 7)),
    proof_workspace=(workspace, True, (5, 6, 7)),
    example=Example(expected="0", kwargs=(("seed", 0),)),
    grid=True,
)
