"""Boolean-function generator for B-tapemark.

One copied cell a row is the walk's target, so a constant run is not folded
or a repeated one shared.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape
from esolangs.tools.helpers import _validate_truth_table, grid_width, input_weights
from esolangs.tools.wrap import balance_score

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
    ) -> None:
        """Place one input's branch, whose ``0`` side adds ``weight``.

        ``run_start`` is the run's first column (default ``x + _RUN_COLUMN``).

        The beam arrives and leaves downwards, and only the ``0`` side
        crosses the run of ``|``, which is what moves the pointer.
        """
        for offset, line in enumerate(lines):
            self.row(x, y + offset, line)
        start = x + _RUN_COLUMN if run_start is None else run_start
        for offset in range(weight):
            self.put(start + offset, y + 1, "|")
        turn = start + weight
        self.put(turn, y + 1, "\\")
        self.put(turn, y + 4, "/")

    def render(self, *, reflect: bool = False) -> str:
        """Render after removing wholly blank rows and columns.

        Each row is drawn from its own cells, only as long as its last
        one, so the cost is the output's size rather than its bounding box.
        Dropping an empty row or column cannot move a beam: a blank cell is
        a no-op wherever it sits.  ``reflect`` mirrors the grid top to
        bottom, mirrors included, which leaves every row's length alone; a
        horizontal mirror is as faithful and is not offered, because it
        moves every ragged edge to the left, where it is rendered.
        """

        def axis(values: set[int], *, reverse: bool = False) -> list[int]:
            # Scanning a dense span beats a comparison sort; the table
            # fills 3T columns, so only sparse layouts sort.
            if not values:
                return []
            lo, hi = min(values), max(values)
            if hi - lo + 1 > 4 * len(values):
                return sorted(values, reverse=reverse)
            order = range(hi, lo - 1, -1) if reverse else range(lo, hi + 1)
            return [v for v in order if v in values]

        xs = axis({x for x, _ in self.cells})
        ys = axis({y for _, y in self.cells}, reverse=reflect)
        column = {x: i for i, x in enumerate(xs)}
        symbols = {"/": "\\", "\\": "/"} if reflect else {}
        rows: dict[int, dict[int, str]] = {y: {} for y in ys}
        for (x, y), char in self.cells.items():
            rows[y][column[x]] = symbols.get(char, char)
        lines = []
        for y in ys:
            cells = rows[y]
            line = [" "] * (max(cells) + 1)
            for i, char in cells.items():
                line[i] = char
            lines.append("".join(line))
        return "\n".join(lines)


def _b_tapemark_narrow(table: str, depth: int, weights: list[int]) -> str:
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
        builder.stage(0, row, weight, _NARROW_STAGE, max(6, 8 - weight))
    # Correct the stages' shared horizontal displacement inside their columns.
    tail = first + _STAGE_ROWS * depth
    builder.put(0, tail, "\\")
    builder.put(depth + 1, tail, "\\")
    builder.put(depth + 1, tail + 1, "/")
    builder.row(0, tail + 1, "!+" + "|" * (depth - 1))
    return builder.render()


def b_tapemark(truth_table: str, width: int | None = None) -> str:
    """Build a B-tapemark program computing ``truth_table``.

    The table is copied onto the blank grid one cell per row, the inputs
    walk the mark pointer to the row they name, and ``+`` prints the mark
    it ends on. When the wide layout exceeds ``width``, a staircase copies one
    entry per row and compact stages retain vertical comparisons. Both
    layouts have O(T) source and construction; narrow XOR2 needs nine columns.
    """
    depth = _validate_truth_table(truth_table)
    # The table is copied at its essential inputs, and an ignored input's
    # stage crosses no ``|``: it still reads and still steps the pointer once,
    # so the climb and tail stay a stage per input.  A constant keeps all.
    weights, painted = input_weights(truth_table, depth)
    if not any(weights):
        painted, weights = truth_table, [1 << (depth - 1 - i) for i in range(depth)]
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
    builder.put(0, 0, "\\")
    for step in range(1, 2 * depth + 1):
        builder.put(0, -step, "|")
    builder.put(0, -2 * depth - 1, "\\")
    builder.put(-1, -2 * depth - 1, "/")

    for stage, weight in enumerate(weights):
        builder.stage(-1, 1 + _STAGE_ROWS * stage, weight)

    # A stage adds one to the pointer whichever way it branches, so the
    # walk overshoots the addressed row by one per stage but the first.
    tail = 1 + _STAGE_ROWS * depth
    builder.put(-1, tail, "/")
    builder.row(-depth - 1, tail, "+" + "|" * (depth - 1))
    builder.put(-depth - 2, tail, "!")
    program = builder.render(reflect=width is not None)
    if width is None or max(map(len, program.splitlines())) <= width:
        return program
    # Narrow width is max(9, T/2+7) columns, under the wide 3T+depth+4.
    # The climb of 2*depth rows must end below the connector at row -1, which
    # a painted table of depth entries or fewer cannot house.
    if len(painted) <= depth:
        painted, weights = truth_table, [1 << (depth - 1 - i) for i in range(depth)]
    return _b_tapemark_narrow(painted, depth, weights)
    return _b_tapemark_narrow(truth_table, depth)


def _balance(table: str, default: str) -> str:
    """Compare the original grid, its reflection and the narrow staircase."""
    return min(
        default,
        b_tapemark(table, grid_width(default)),
        b_tapemark(table, 1),
        key=balance_score,
    )


LANGUAGE = Language(
    "B-tapemark",
    "grid_based.b_tapemark",
    boolean=b_tapemark,
    # Not a tree: the table copied onto the grid, one mark per row.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    empty_program="B-tapemark program needs exactly one start marker",
)
