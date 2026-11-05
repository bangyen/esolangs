"""B-tapemark Boolean program generator: a copied table walked by weighted stages.

The table is copied onto the blank grid, one cell per row; each input's stage
walks the mark pointer by its weight when the bit is 0, and ``+`` prints the
mark it ends on.  Constant roots read all inputs into disposable marks and
print a literal answer without that walk.

The ``swap_marker="old"`` dialect rebuilds each stage around its own
round-trip landing (see :meth:`_Builder._stage_old`); the copy phase, the
climb and the tail are shared, and on the measured corpus its programs are
no larger than the default dialect's.

Size:
    Figures are measured on the default dialect (swap_marker='new').
    O(T) source and construction in every layout; the narrow XOR2 needs
    nine columns. Constants: 2n + 2 cells in one row. The default is the least
    by area of the wide strip and the
    closed-form strips (no width sweep): n=10
    parity: 13,741 chars, n=10 random 1847: 13,741 chars, a 54 x 307 grid
    against the strip's 93 x 3,086 (6,809 chars of ragged rows).
    ``balance`` snakes the copy and the weight runs into strips
    (:func:`_b_tapemark_folded`): n=6 random 202 -> 118 on a side, n=10
    3086 -> 243; the stages' seven rows apiece floor the height.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isqrt

from esolangs.generation.helpers import (
    _validate_truth_table,
    grid_rank,
    grid_width,
    input_weights,
)
from esolangs.generation.wrap import balance_score
from esolangs.languages.b_tapemark.interpreter import (
    SWAP_MARKERS,
    validate_swap_marker,
)
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

#: The stage, row by row, with its run of ``|`` left out.  The two ``*``
#: copy a ``\`` and a ``%`` onto the blank grid beside the pointer, ``-``
#: reads the input digit into the pointer's own cell, and ``0`` compares:
#: a match swaps onto the copied pair, which turns the beam and swaps
#: straight back, so the answers leave the compare travelling in different
#: directions.  They rejoin at the last row's ``*``, which skips the arm
#: the other one turns on.
_STAGE = (
    "|/    \\",
    "*\\-|\\ 0",
    "\\   | |",
    "\\|*%/ \\|\\",
    "    /",
    "/   /*  /",
    "|",
)

#: Rows one branch stage occupies, and so the stride between stages.
_STAGE_ROWS = len(_STAGE)

#: The narrow layout's stage: the same rows, packed into fewer columns.
_NARROW_STAGE = (
    "|/   \\",
    "*\\-|\\0",
    "\\   ||",
    "\\|*%/\\|\\",
    "    /",
    "/   /* /",
    "|",
)

#: Column the run of ``|`` starts at, clear of the cells the untaken side
#: uses to rejoin.
_RUN_COLUMN = 9


@dataclass
class _Builder:
    """Place cells on the program grid and render the result."""

    cells: dict[tuple[int, int], str] = field(default_factory=dict)

    def put(self, x: int, y: int, char: str) -> None:
        """Place ``char``, rejecting a conflicting placement."""
        previous = self.cells.setdefault((x, y), char)
        if previous != char:
            raise AssertionError(f"layout collision at {(x, y)}")

    def row(self, x: int, y: int, text: str) -> None:
        """Place ``text`` rightwards from ``(x, y)``, skipping its blanks."""
        for offset, char in enumerate(text):
            if char != " ":
                self.put(x + offset, y, char)

    def stage(
        self,
        x: int,
        y: int,
        weight: int,
        lines: tuple[str, ...] = _STAGE,
        run_start: int | None = None,
        *,
        swap_marker: str = "new",
    ) -> None:
        """Place one input's branch, whose ``0`` side adds ``weight``.

        ``run_start`` is the run's first column (default ``x + _RUN_COLUMN``).

        The beam arrives and leaves downwards, and only the ``0`` side
        crosses the run of ``|``, which is what moves the pointer.
        """
        if swap_marker == "old":
            self._stage_old(x, y, weight, lines)
            return
        for offset, line in enumerate(lines):
            self.row(x, y + offset, line)
        start = x + _RUN_COLUMN if run_start is None else run_start
        for offset in range(weight):
            self.put(start + offset, y + 1, "|")
        turn = start + weight
        self.put(turn, y + 1, "\\")
        self.put(turn, y + 4, "/")

    def _stage_old(self, x: int, y: int, weight: int, lines: tuple[str, ...]) -> None:
        """Place one input's branch for the ``old`` swap-marker dialect.

        Under ``old`` the match side's round trip leaves the beam on the
        compare column's next row, heading east across the very ``|``
        the other side steps south through, and the pointer two columns
        further east than the other side's own dance leaves it: the
        walk still owed is ``weight - 2``, taken as a run of ``|`` on
        that row (or, for weight under 2, as west-stepping ``|`` on
        the funnel row, clear of the other side's south crossing).
        The beam turns south past the stage's last row-3 cell and
        rejoins the shared funnel at row 4's ``/``.
        """
        for offset, line in enumerate(lines):
            self.row(x, y + offset, line)
        landing = 5 if lines is _NARROW_STAGE else 6
        run = max(0, weight - 2)
        for offset in range(run):
            self.put(x + landing + 1 + offset, y + 2, "|")
        turn = x + max(landing + 3, landing + 1 + run)
        self.put(turn, y + 2, "\\")
        self.put(turn, y + 4, "/")
        if weight == 1:
            self.put(x + landing + 1, y + 4, "|")
        elif weight == 0:
            self.put(x + landing + 1, y + 4, "|")
            self.put(x + landing, y + 4, "|")

    def climb(self, y: int, depth: int) -> None:
        """Turn up at ``(0, y)`` into the ``2 * depth`` climb above the copy."""
        self.put(0, y, "\\")
        for step in range(1, 2 * depth + 1):
            self.put(0, -step, "|")
        self.put(0, -2 * depth - 1, "\\")
        self.put(-1, -2 * depth - 1, "/")

    def finish(self, y: int, depth: int) -> None:
        """Close on row ``y``: the ``/``, the printing ``+`` run and ``!``."""
        self.put(-1, y, "/")
        self.row(-depth - 1, y, "+" + "|" * (depth - 1))
        self.put(-depth - 2, y, "!")

    def render(self, *, reflect: bool = False) -> str:
        """Render the bounding box of the placed cells.

        ``reflect`` mirrors the grid top to bottom, mirrors included.  Dropping
        wholly blank rows and columns was retired: it never fired.
        """

        def axis(values: set[int], *, reverse: bool = False) -> list[int]:
            if not values:
                return []
            lo, hi = min(values), max(values)
            return list(range(hi, lo - 1, -1) if reverse else range(lo, hi + 1))

        xs = axis({x for x, _ in self.cells})
        ys = axis({y for _, y in self.cells}, reverse=reflect)
        column = {x: i for i, x in enumerate(xs)}
        # Reflecting leaves every row's length alone.  A horizontal mirror is
        # as faithful but not offered: it moves every ragged edge to the left,
        # where it is rendered.
        symbols = {"/": "\\", "\\": "/"} if reflect else {}
        rows: dict[int, dict[int, str]] = {y: {} for y in ys}
        for (x, y), char in self.cells.items():
            rows[y][column[x]] = symbols.get(char, char)
        # Each row is drawn only as far as its last cell, so cost is the
        # output's size, not its bounding box.
        lines = []
        for y in ys:
            cells = rows[y]
            line = [" "] * (max(cells, default=-1) + 1)
            for i, char in cells.items():
                line[i] = char
            lines.append("".join(line))
        return "\n".join(lines)


def _b_tapemark_narrow(
    table: str, depth: int, weights: list[int], swap_marker: str = "new"
) -> str:
    """Narrow layout: copy on a staircase, compares vertical, indices horizontal.

    ``table`` is painted at the essential inputs; ``weights`` has one stage
    per input, an ignored one crossing no ``|``.
    """
    builder = _Builder()
    # The copy beam always travels west; only the connector reverses it.
    for index, bit in enumerate(table):
        row = 2 * index
        builder.row(2, row, f"|{bit}*")
        builder.put(1, row, "/")
        builder.put(5, row, "<" if index == 0 else "/")
        if index + 1 < len(table):
            builder.put(1, row + 1, "\\")
            builder.put(5, row + 1, "\\")
    bottom = 2 * len(table) - 1
    builder.put(1, bottom, "\\")
    builder.put(6, bottom, "/")
    for offset in range(1, 2 * depth + 1):
        builder.put(6, bottom - offset, "|")
    # The climb is outside copy columns 1..5; descent uses empty column 0.
    builder.put(6, -1, "\\")
    builder.put(0, -1, "/")
    first = bottom + 1
    for level in range(depth):
        row = first + _STAGE_ROWS * level
        weight = weights[level]
        # Column 8 clears the other arm's turn in column 7, even at weight 1.
        builder.stage(
            0, row, weight, _NARROW_STAGE, max(6, 8 - weight), swap_marker=swap_marker
        )
    # Correct the stages' shared horizontal displacement inside their columns.
    tail = first + _STAGE_ROWS * depth
    builder.put(0, tail, "\\")
    builder.put(depth + 1, tail, "\\")
    builder.put(depth + 1, tail + 1, "/")
    builder.row(0, tail + 1, "!+" + "|" * (depth - 1))
    return builder.render()


def _dialect(swap_marker: str = "new") -> None:
    """Validate which grid's marker moves after a swap."""
    validate_swap_marker(swap_marker)


def b_tapemark(
    truth_table: str, width: int | None = None, *, swap_marker: str = "new"
) -> str:
    """Build a B-tapemark program computing ``truth_table``.

    The table is copied onto the blank grid one cell per row, the inputs
    walk the mark pointer to the row they name, and ``+`` prints the mark
    it ends on. When the wide layout exceeds ``width``, a staircase copies one
    entry per row and compact stages retain vertical comparisons. Both
    layouts have O(T) source and construction; narrow XOR2 needs nine columns.

    ``swap_marker`` selects the dialect the stages are built for (see the
    interpreter's ``Dialects`` note); the constant layout swaps nothing
    and serves both.
    """
    validate_swap_marker(swap_marker)
    depth = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        answer = truth_table[0]
        horizontal = ">" + "-|" * (depth - 1) + "-" + answer + "!"
        if width is None or len(horizontal) <= width:
            return horizontal
        # Each vertical | moves to a fresh mark; the final mirror turns right
        # so the literal digit prints rather than comparing the data mark.
        return "v\n" + "-\n|\n" * (depth - 1) + "-\n\\" + answer + "!"
    program = _b_tapemark_program(truth_table, width)
    program = _b_tapemark_program(truth_table, width, swap_marker=swap_marker)
    if width is not None:
        return program
    # Judged by area: the wide strip or the least of the closed-form layouts.
    # No width sweep, so O(T).  See [ablations.area_default].
    return min([program, *_closed_forms(truth_table, swap_marker)], key=grid_rank)


def _b_tapemark_program(
    truth_table: str,
    width: int | None = None,
    *,
    keep_full_narrow: bool = False,
    swap_marker: str = "new",
) -> str:
    """Build the copied-table walk, retaining the former constant layout."""
    depth = _validate_truth_table(truth_table)
    # The table is copied at its essential inputs, and an ignored input's
    # stage crosses no ``|``: it still reads and still steps the pointer once,
    # so the climb and tail stay a stage per input.  A constant keeps all.
    weights, painted = input_weights(truth_table, depth)
    full = [1 << (depth - 1 - i) for i in range(depth)]
    if not any(weights):
        painted, weights = truth_table, full
    size = len(painted)
    builder = _Builder()

    # Rightmost row first: the beam runs leftwards and the pointer trails
    # it, ``*`` copying the digit it skips and ``|`` stepping the pointer.
    for index, bit in enumerate(painted):
        builder.row(1 + 3 * (size - 1 - index), 0, f"|{bit}*")
    builder.put(3 * size + 1, 0, "<")

    # The copy leaves the pointer on the table's row, where nothing is
    # blank, and a stage needs blank cells to read and copy into: so the
    # pointer climbs clear and the stages walk it back down a row apiece,
    # landing on the table again exactly as they run out.
    builder.climb(0, depth)

    for stage, weight in enumerate(weights):
        builder.stage(-1, 1 + _STAGE_ROWS * stage, weight, swap_marker=swap_marker)

    # A stage adds one to the pointer whichever way it branches, so the
    # walk overshoots the addressed row by one per stage but the first.
    tail = 1 + _STAGE_ROWS * depth
    builder.finish(tail, depth)
    program = builder.render(reflect=width is not None)
    if width is None or grid_width(program) <= width:
        return program
    # Narrow width is max(9, T/2+7) columns, under the wide 3T+depth+4.
    # The climb of 2*depth rows must end below the connector at row -1, which
    # a painted table of depth entries or fewer cannot house.
    if len(painted) <= depth:
        if keep_full_narrow:
            painted, weights = truth_table, full
        else:
            # The zero-side weights count back from the final copied cell.
            # Unaddressed cells before the projected table house the climb
            # without restoring ignored selectors or their exponentially
            # larger table; padding after it shifts every addressed answer.
            painted = "0" * (depth + 1 - len(painted)) + painted
    return _b_tapemark_narrow(painted, depth, weights, swap_marker)


def _folded_stage_old(builder: _Builder, top: int, weight: int, run: int) -> int:
    """Place one folded stage for the ``old`` dialect; return the next top.

    The run owed is ``weight - 2`` (see :meth:`_Builder._stage_old`),
    snaking east from the shipped run's first column on the landing row
    and the blank rows inserted after row 3, so a segment holds ``run``
    cells to the shipped east extent; the funnel row is stage row 4's,
    past the inserted band.
    """
    total = max(0, weight - 2)
    segments = [run] * (total // run) + ([total % run] if total % run else [])
    inserted = max(0, 2 * len(segments) - 3) if segments else 0
    for offset, line in enumerate(_STAGE):
        builder.row(-1, top + offset + (inserted if offset >= 4 else 0), line)
    start, link = -1 + _RUN_COLUMN + 1, -1 + _RUN_COLUMN
    if not segments:
        builder.put(link, top + 2, "\\")
        builder.put(link, top + 4, "/")
    for fold, length in enumerate(segments):
        row = top + 2 + 2 * fold
        for col in range(start, start + length):
            builder.put(col, row, "|")
        builder.put(start + length, row, "\\")
        if fold + 1 < len(segments):
            builder.put(start + length, row + 1, "/")
            builder.put(link, row + 1, "/")
            builder.put(link, row + 2, "\\")
        else:
            builder.put(start + length, top + 4 + inserted, "/")
    if weight == 1:
        builder.put(start - 3, top + 4 + inserted, "|")
    elif weight == 0:
        builder.put(start - 3, top + 4 + inserted, "|")
        builder.put(start - 4, top + 4 + inserted, "|")
    return top + _STAGE_ROWS + inserted


def _b_tapemark_folded(
    truth_table: str, copy: int, run: int, swap_marker: str = "new"
) -> str:
    """Build the copied-table walk with its long rows snaked into strips.

    The copy and the weight runs each act in one direction only (``|``
    moves the pointer with the beam), so ``copy`` entries go per westward
    row and at most ``run`` ``|`` per eastward row, each pair joined by a
    blank row back: the data table stays one row and the stages' arithmetic
    is unchanged.  A stage's runs take its rows 1 and 3, then blank rows
    inserted after row 3, which every beam crosses straight down.
    """
    depth = _validate_truth_table(truth_table)
    weights, painted = input_weights(truth_table, depth)
    builder = _Builder()

    # Strip k holds entries k*copy.. on row 2k, read westward from x_east;
    # an eastward blank row 2k+1 joins it to the next via column 1.
    east = 2 + 3 * copy
    strips = -(-len(painted) // copy)
    for index, bit in enumerate(painted):
        strip, slot = divmod(index, copy)
        builder.row(east - 3 - 3 * slot, 2 * strip, f"|{bit}*")
    builder.put(east, 0, "<")
    for strip in range(strips - 1):
        row = 2 * strip
        builder.put(1, row, "/")
        builder.put(1, row + 1, "\\")
        builder.put(east, row + 1, "\\")
        builder.put(east, row + 2, "/")
    last = 2 * (strips - 1)
    builder.climb(last, depth)

    top = last + 1
    for weight in weights:
        if swap_marker == "old":
            top = _folded_stage_old(builder, top, weight, run)
            continue
        rows = [run] * (weight // run) + ([weight % run] if weight % run else [])
        rows = rows or [0]
        inserted = max(0, 2 * len(rows) - 4)
        for offset, line in enumerate(_STAGE):
            builder.row(-1, top + offset + (inserted if offset >= 4 else 0), line)
        start, link = -1 + _RUN_COLUMN + 1, -1 + _RUN_COLUMN
        for fold, length in enumerate(rows):
            row = top + 1 + 2 * fold
            for col in range(start, start + length):
                builder.put(col, row, "|")
            builder.put(start + length, row, "\\")
            if fold + 1 < len(rows):
                builder.put(start + length, row + 1, "/")
                builder.put(link, row + 1, "/")
                builder.put(link, row + 2, "\\")
            else:
                builder.put(start + length, top + 4 + inserted, "/")
        top += _STAGE_ROWS + inserted

    builder.finish(top, depth)
    return builder.render()


def _closed_forms(table: str, swap_marker: str = "new") -> list[str]:
    """Return the formula's folded strips (not constant)."""
    candidates: list[str] = []
    depth = len(table).bit_length() - 1
    # A run row as wide as a copy row (3 per entry, less the stage's 12
    # columns west of it) won at n=7..10 in a full grid; below that the
    # stages' 7 rows apiece floor the height and runs go unfolded.
    # Folded, the width is 3 * copy + 13 and the height 2T / copy + 9n + 2
    # rows (measured n=6..10); the side is least where the width meets twice
    # the height, 3c^2 + (9 - 18n)c - 4T = 0.
    half = 18 * depth - 9
    best = (half + isqrt(half * half + 48 * len(table))) // 6
    # The area model balances its terms proportional to n*c and T/c.
    # Its practical win is an explicit exception to the sustained-share bar
    # ([ablations.area_strip_width_prototype]); the side-fit forms still balance.
    area_copy = max(5, isqrt(104 * len(table) // (63 * depth)))
    candidates.extend(
        _b_tapemark_folded(table, max(1, copy), max(1, 3 * copy - 12), swap_marker)
        for copy in {best, best * 17 // 20, area_copy}
    )
    return candidates


def _balance(table: str, default: str, *, swap_marker: str = "new") -> str:
    """Return the default or the closed-form layout with the least balanced side."""
    if len(set(table)) == 1:
        return default
    # Preserve the wide form that the old default supplied on small tables.
    return min(
        [
            default,
            _b_tapemark_program(table, swap_marker=swap_marker),
            *_closed_forms(table, swap_marker),
        ],
        key=balance_score,
    )


LANGUAGE = Language(
    "B-tapemark",
    RuntimeSpec(
        "b_tapemark",
        category="grid_based",
        dialect=_dialect,
        dialect_values={"swap_marker": SWAP_MARKERS},
        empty_program="B-tapemark program needs exactly one start marker",
    ),
    backend=BooleanBackend(
        generate=b_tapemark,
        # Not a tree: the table copied onto the grid, one mark per row.
        shape=Shape.LOOKUP,
        balance=_balance,
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
