"""The LaserFuck boolean generator."""

from functools import cache
from typing import NamedTuple

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    grid_width,
    input_orders,
    input_weights,
    level_cells,
    move_text,
    narrowest_grid,
    permute_truth_table,
    subtree_ids,
)

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


def _laserfuck_reads(perm: tuple[int, ...]) -> str:
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
    # A node ``>#v)`` steps the pointer, then tests: level k tests cell k + 1.
    cells = level_cells(perm)
    out = ""
    at = 1
    for cell in cells:
        out += move_text(at, cell, ">", "<") + ","
        at = cell
    return out + move_text(at, 0, ">", "<")


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
    reads = _laserfuck_reads(tuple(range(n)) if perm is None else perm)
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

    The beam arrives and leaves travelling *right*.  ``rows`` are the
    block's cells, laid ``top`` rows below the origin; ``connectors`` are
    extra ``(row, col, char)`` cells that steer the beam in and out;
    ``exit_row``/``exit_col`` are the offsets from the origin to the cell
    the next block starts from.  A flat block needs no connectors; a rotated
    one is entered from above and left from below, so it sits one row down
    with two connectors.
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


def _laserfuck_placements(
    n: int,
    perm: tuple[int, ...] | None = None,
) -> list[dict[str, _LaserBlock]]:
    """Place every reader block in *both* orientations, once.

    The caller tries all ``2**count`` orientation words, and a block's
    placement depends only on the block and its own letter -- so cutting
    and rotating per word rebuilt the same ``2 * count`` placements
    ``2**count`` times.  Hoisting them turns 17 reader cuts and 16 rotations
    at n=6 into one and two per candidate.
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

    # Bucket by row and fill gaps: probing the bounding rectangle is
    # 5.8M dict lookups on a mostly-blank six-input grid.
    height = max(r for r, _ in cells) + 1
    rows: list[list[tuple[int, str]]] = [[] for _ in range(height)]
    for (r, c), char in cells.items():
        rows[r].append((c, char))
    return [_laserfuck_join(sorted(marks))[0] for marks in rows], row, col


def _laserfuck_join(marks: list[tuple[int, str]]) -> tuple[str]:
    """Join ``(column, text)`` runs left to right, padding gaps with blanks."""
    parts: list[str] = []
    cursor = 0
    for col, text in marks:
        parts.append(" " * (col - cursor) + text)
        cursor = col + len(text)
    return ("".join(parts),)


_ReaderCandidate = tuple[int, int, tuple[str, ...], int, int]


@cache
def _laserfuck_reader_candidates(
    n: int,
    perm: tuple[int, ...] | None = None,
) -> tuple[_ReaderCandidate, ...]:
    """Every orientation word's reader, shortest first, as ``(rows, span, ...)``.

    The search depends on ``n`` and ``perm`` alone -- a truth table never
    reaches the reader, and a width only *filters* the result -- so every
    build at one arity and order rebuilt the same ``2**count`` readers.
    Caching it hoists the search out of the per-build path the way
    :func:`_laserfuck_placements` hoisted the cuts out of the per-word one.
    Rows come back as tuples because the callers only read them.
    """
    placements = _laserfuck_placements(n, perm)
    count = len(placements)
    candidates = []
    for choice in range(2**count):
        orientation = "".join("R" if choice >> b & 1 else "F" for b in range(count))
        rows_of, exit_row, exit_col = _laserfuck_assemble_reader(
            placements, orientation
        )
        span = max(len(line) for line in rows_of)
        candidates.append((len(rows_of), span, tuple(rows_of), exit_row, exit_col))
    # Stable, so ties still break on the orientation word's own order.
    candidates.sort(key=lambda item: (item[0], item[1]))
    return tuple(candidates)


class _LaserReader(NamedTuple):
    rows: tuple[str, ...]
    exit_row: int
    exit_col: int


class _LaserTree(NamedTuple):
    runs: list[list[tuple[int, str]]]
    upright: list[str]


def _laserfuck_reader(
    n: int, perm: tuple[int, ...], width: int | None, *, vertical_tree: bool
) -> _LaserReader:
    """Select the reader placement and its outgoing beam position."""
    # The tree adds only a column or two past the reader, so the reader is
    # what a width has to bargain with: side by side the rings are one row
    # and forty-odd columns, stacked they are seven rows and under twenty.
    reader_rows: list[str] | tuple[str, ...]
    if vertical_tree:
        placements = _laserfuck_placements(n, perm)
        reader_rows, reader_exit_row, reader_exit_col = _laserfuck_assemble_reader(
            placements, "R" * len(placements)
        )
    else:
        candidates = _laserfuck_reader_candidates(n, perm)
        fitting = [
            item
            for item in candidates
            if width is None or MARGIN + item[1] + 2 <= width
        ]
        chosen = fitting[0] if fitting else min(candidates, key=lambda item: item[1])
        _, _, reader_rows, reader_exit_row, reader_exit_col = chosen

    return _LaserReader(tuple(reader_rows), reader_exit_row, reader_exit_col)


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


def _laserfuck_tree(truth_table: str, n: int, *, fold: bool = True) -> _LaserTree:
    """Emit the decision-tree runs and their padded upright block."""
    # The tree is built as its own block, mirrored, and hung under the
    # reader: the beam turns down at the reader's end and a '/' faces it
    # left, so no return row is needed to reach a rightward tree.
    # A node is ``>#v)``: '#' skips the 'v' going in, ')' tests the cell; a
    # zero continues on the row, a one turns back onto 'v' and drops to a
    # '\' on a fresh row.  Rows scale with *one* edges, not nodes.
    # Rows are ``(column, text)`` runs, filled left to right with no blanks
    # (``><-+``, ``x``, ``>#v)``, ``\``); the old n! order search paid a
    # cell dict twice over a mostly-blank staircase.  A row is appended
    # exactly when a ``one`` edge creates it, so ``len(rows)`` is the next index.
    rows: list[list[tuple[int, str]]] = [[]]

    constant = constant_span_test(truth_table)
    ids = subtree_ids(truth_table)

    def emit(depth: int, first: int, row: int, col: int, skipped: int = 0) -> None:
        """Lay one row span, entered at ``(row, col)`` going right.

        ``skipped`` has bit ``d`` set where level ``d`` took no test.
        """
        stop = first + 2 ** (n - depth)
        if depth == n or constant(first, stop):
            index = first
            # Inputs sit in cells 1..n, cell 0 at zero, so a zero answer
            # needs no code.  Sweep all ``n`` cells from cell ``n`` down or
            # an unconsumed one prints beside the answer: cells above
            # ``depth`` are unknown, two ``-`` retire either (0 -> -2, 1 -> -1);
            # consumed cells keep the sized run, so an unfolded table is unchanged.
            run = ">" * (n - depth)
            run += "--<" * (n - depth)
            for level in range(depth, 0, -1):
                bit = (first >> (n - level)) & 1
                # A level without a test left its cell unknown: flat ``--``.
                run += "-" * (2 if skipped >> (level - 1) & 1 else bit + 1) + "<"
            run += "+" if truth_table[index] == "1" else ""
            rows[row].append((col, run + "x"))
            return
        below = ids[depth + 1]
        place = first >> (n - depth)
        if fold and below[2 * place] == below[2 * place + 1]:
            # Equal halves (an ignored input, a repeat): the input is still
            # read, so step the pointer past its cell, but test nothing.
            rows[row].append((col, ">"))
            emit(depth + 1, first, row, col + 1, skipped | 1 << depth)
            return
        rows[row].append((col, ">#v)"))
        emit(depth + 1, first, row, col + 4, skipped)  # zero carries on
        drop = len(rows)
        rows.append([(col + 2, "\\")])  # a one comes down the 'v' column
        emit(depth + 1, first + 2 ** (n - depth - 1), drop, col + 3, skipped)

    emit(0, 0, 0, 0)
    span = max(col + len(text) for marks in rows for col, text in marks)
    upright = [_laserfuck_join(marks)[0].ljust(span) for marks in rows]

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
    perm: tuple[int, ...],
    width: int | None = None,
    *,
    vertical_tree: bool = False,
    fold: bool = True,
) -> str:
    r"""Build one LaserFuck program, placing inputs in ``perm`` tape order.

    ``truth_table`` is already permuted, so every row index here is in the
    permuted frame; ``perm`` is spent only in the reader's read section.

    The laser starts at ``o`` with a random heading, so a mirror funnel
    (``|``/``^``/``_`` plus two ``}`` on the row above) sends every heading
    to the top row moving right, into the reader and then the tree (see
    :func:`_laserfuck_ring_reader`, :func:`_laserfuck_tree`).  Rows scale
    with the number of *one* edges, and the all-zeros path is one line.

    A subtree whose rows all agree becomes a leaf.  Only the cells above a
    leaf's depth are unknown, so a flat two ``-`` retires either value
    (0 -> -2, 1 -> -1) while consumed cells keep the sized run.  The sweep
    still covers all ``n`` cells, since an unconsumed one sits at 0 or 1 and
    would print beside the answer.

    LaserFuck prints the tape when the last laser dies, in decimal, skipping
    negative cells.  Cell (0, 0) is left blank deliberately -- a ``\\xff``
    there would select byte mode.

    ``width`` bounds the columns.  When the flat reader will not fit,
    :func:`_laserfuck_rotate` stands it on end; below the width the *tree*
    needs, the grid comes out as wide as the tree.
    """
    n = _validate_truth_table(truth_table)
    reader = _laserfuck_reader(n, perm, width, vertical_tree=vertical_tree)
    reader_rows = reader.rows

    margin = MARGIN
    grid = _LaserGrid()

    # The funnel: every start heading ends up on row 0 moving right.  Cell
    # (0, 0) stays blank so the tape dumps in decimal rather than byte mode.
    grid.put(0, 1, "}")
    grid.put(0, 2, "}")
    grid.put(1, 0, "|")
    grid.put(1, 1, "o")
    grid.put(1, 2, "^")
    grid.put(2, 1, "_")

    # The rings go on rows 0 and 1; the beam leaves them still moving right
    # with the pointer on cell 0.
    for offset, text in enumerate(reader_rows):
        for index, char in enumerate(text):
            if char != " ":
                grid.put(offset, margin + index, char)
    tree = _laserfuck_tree(truth_table, n, fold=fold)
    _laserfuck_attach_tree(grid, reader, tree, width, vertical_tree=vertical_tree)
    return grid.render()


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

    Without a width, the natural layout is built; the narrowest-reader
    (``width=1``) layout is 21.3% shorter by length at n=4 but doubles the
    area (-106.7%), so it is not tried.  The greedy order saves 12.3% of
    area at n=4.

    A constant span is one leaf and a node whose halves agree is passed over.
    A leaf retires the cells it consumed by the bits on its path (``-`` x
    bit+1), so equal subtrees are different code under different parents:
    none is shared.

    A width is applied to every candidate rather than to the winner: the
    reader's orientations and the tree's placement already trade rows
    against columns, so the narrowest program is often not the shortest,
    and the choice has to be made over the whole pool.
    """
    _validate_truth_table(truth_table)
    if width is None and len(truth_table) > 16:
        return _laserfuck_weighted(truth_table)
    # Folding equal halves (ignored inputs, repeats) drops tests but moved a
    # width layout's area up 7 of ~500 on some n=3 tables, so under a width
    # the unfolded build stays a candidate, judged by area.
    built = [
        _laserfuck_pool(truth_table, width, fold=fold)
        for fold in ((True,) if width is None else (True, False))
    ]
    return min(built, key=lambda form: _laserfuck_rank(form, width))


def _laserfuck_rank(program: str, width: int | None) -> tuple[int, int]:
    """Rank by columns past the request, then area (rows times widest row)."""
    span = grid_width(program)
    return (0 if width is None else max(span, width), len(program.splitlines()) * span)


def _laserfuck_pool(truth_table: str, width: int | None, *, fold: bool) -> str:
    """Return the best candidate over input orders, tree placements and fold."""
    orders = input_orders(truth_table)
    identity = orders[0]

    best = _laserfuck_build(truth_table, identity, width, fold=fold)
    for perm in orders[1:]:
        candidate = _laserfuck_build(
            permute_truth_table(truth_table, perm), perm, width, fold=fold
        )
        if len(candidate) < len(best):
            best = candidate
    if width is not None and grid_width(best) > width:
        # Move the start funnel above the computation, reclaiming its three
        # reserved columns. Two '/' turns enter its first heading setter.
        best = _laserfuck_raise_funnel(best)
        # Turning the staircase upright costs O(T log T) padding in general;
        # this bounded fallback keeps the full family O(T).
        if grid_width(best) > width and len(truth_table) <= 8:
            candidate = _laserfuck_build(
                truth_table, identity, width, vertical_tree=True, fold=fold
            )
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
    for row, col, char in (
        (0, 1, "}"),
        (0, 2, "}"),
        (0, 3, "v"),
        (1, 0, "|"),
        (1, 1, "o"),
        (1, 2, "^"),
        (2, 1, "_"),
        (3, 3, "{"),
        (3, 2, "v"),
    ):
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
    orders = input_orders(table)
    regimes = [(permute_truth_table(table, perm), perm) for perm in orders]
    margin = MARGIN
    events = {1, 4}
    for ordered, perm in regimes:
        tree = _laserfuck_tree(ordered, n)
        span = max(map(len, tree.upright))
        for _, columns, _, _, exit_column in _laserfuck_reader_candidates(n, perm):
            events.update((margin + columns + 2, margin + exit_column + span + 1))
    boundaries = sorted(events)
    widths = set(boundaries)
    for index, start in enumerate(boundaries):
        stop = boundaries[index + 1] if index + 1 < len(boundaries) else None
        forms = [_laserfuck_build(ordered, perm, start) for ordered, perm in regimes]
        if len(table) <= 8:
            forms.append(_laserfuck_build(table, orders[0], start, vertical_tree=True))
        # Reader and tree geometry is fixed within this interval. Only the
        # source's own fit can switch its startup funnel or narrow fallback.
        spans = {grid_width(form) for form in forms}
        spans.update(grid_width(_laserfuck_raise_funnel(form)) for form in forms)
        widths.update(
            span for span in spans if start < span and (stop is None or span < stop)
        )
    # Local: a module-level import changes the dump's callable keys.
    from esolangs.tools.wrap import balance_score

    return min(
        default,
        *(laserfuck(table, width) for width in sorted(widths)),
        key=balance_score,
    )
