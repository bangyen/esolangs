"""B-tapemark Boolean program generator: a copied table walked by weighted stages.

The table is copied onto the blank grid, one cell per row; each input's stage
walks the mark pointer by its weight when the bit is 0, and ``+`` prints the
mark it ends on.  Constant roots read all inputs into disposable marks and
print a literal answer without that walk.

Size:
    O(T) source and construction in both layouts; the narrow XOR2 needs
    nine columns.  n=10 parity: 6,809 chars, n=10 random 1847: 6,809 chars.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from esolangs.generation.helpers import _validate_truth_table, grid_width, input_weights
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

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
        """Render without wholly blank rows and columns.

        ``reflect`` mirrors the grid top to bottom, mirrors included.
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

        # Dropping an empty row or column cannot move a beam: a blank cell is
        # a no-op anywhere.
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
    if len(set(truth_table)) == 1:
        answer = truth_table[0]
        horizontal = ">" + "-|" * depth + answer + "!"
        if width is None or len(horizontal) <= width:
            return horizontal
        # Each vertical | moves to a fresh mark; the final mirror turns right
        # so the literal digit prints rather than comparing the data mark.
        return "v\n" + "-\n|\n" * depth + "\\" + answer + "!"
    return _b_tapemark_program(truth_table, width)


def _b_tapemark_program(
    truth_table: str, width: int | None = None, *, keep_full_narrow: bool = False
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
    return _b_tapemark_narrow(painted, depth, weights)


def _balance(table: str, default: str) -> str:
    """Compare the original grid, its reflection and the narrow staircase."""
    if len(set(table)) == 1:
        legacy = _b_tapemark_program(table, keep_full_narrow=True)
        return min(
            default,
            b_tapemark(table, 1),
            legacy,
            _b_tapemark_program(table, grid_width(legacy), keep_full_narrow=True),
            _b_tapemark_program(table, 1, keep_full_narrow=True),
            key=balance_score,
        )
    candidates = [
        default,
        b_tapemark(table, grid_width(default)),
        b_tapemark(table, 1),
    ]
    depth = len(table).bit_length() - 1
    if len(input_weights(table, depth)[1]) <= depth:
        candidates.extend(
            [
                _b_tapemark_program(table, grid_width(default), keep_full_narrow=True),
                _b_tapemark_program(table, 1, keep_full_narrow=True),
            ]
        )
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "B-tapemark",
    "b_tapemark",
    category="grid_based",
    boolean=b_tapemark,
    # Not a tree: the table copied onto the grid, one mark per row.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    balance=_balance,
    empty_program="B-tapemark program needs exactly one start marker",
)
