"""Boolean-function generator for B-tapemark."""

from __future__ import annotations

from dataclasses import dataclass, field

from esolangs.tools.helpers import _validate_truth_table

#: Rows one branch stage occupies, and so the stride between stages.
_STAGE_ROWS = 7

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

    def stage(self, x: int, y: int, weight: int) -> None:
        """Place one input's branch, whose ``0`` side adds ``weight``.

        The beam arrives and leaves downwards, and only the ``0`` side
        crosses the run of ``|``, which is what moves the pointer.
        """
        for offset, line in enumerate(_STAGE):
            self.row(x, y + offset, line)
        for offset in range(weight):
            self.put(x + _RUN_COLUMN + offset, y + 1, "|")
        turn = x + _RUN_COLUMN + weight
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
        xs = sorted({x for x, _ in self.cells})
        ys = sorted({y for _, y in self.cells}, reverse=reflect)
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


def b_tapemark(truth_table: str, width: int | None = None) -> str:
    """Build a B-tapemark program computing ``truth_table``.

    The table is copied onto the blank grid one cell per row, the inputs
    walk the mark pointer to the row they name, and ``+`` prints the mark
    it ends on.  A requested ``width`` selects the mirrored grid: the copy
    is one line as long as the table, so no narrower bound can be honoured
    by any orientation.
    """
    depth = _validate_truth_table(truth_table)
    size = len(truth_table)
    builder = _Builder()

    # Rightmost row first: the beam runs leftwards and the pointer trails
    # it, ``*`` copying the digit it skips and ``|`` stepping the pointer.
    for index, bit in enumerate(truth_table):
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

    for stage, weight in enumerate(2**place for place in reversed(range(depth))):
        builder.stage(-1, 1 + _STAGE_ROWS * stage, weight)

    # A stage adds one to the pointer whichever way it branches, so the
    # walk overshoots the addressed row by one per stage but the first.
    tail = 1 + _STAGE_ROWS * depth
    builder.put(-1, tail, "/")
    builder.row(-depth - 1, tail, "+" + "|" * (depth - 1))
    builder.put(-depth - 2, tail, "!")
    return builder.render(reflect=width is not None)
