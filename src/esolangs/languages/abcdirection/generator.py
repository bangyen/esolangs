"""Boolean program generator for ABCDirection.

The table, read at its ``k`` essential inputs, goes onto the tape, and the
inputs walk the tape pointer to the answer; the grid draws no tree.

- **Write.**  One row heading left runs a ``C`` per entry (step right; the
  fresh cell becomes 1), then a ``D`` after a 0 entry (dequeue the empty
  queue: 0).  Entry ``r`` lands ``r`` cells right of entry 0, and a last
  ``C`` steps onto the *dead* cell right of the final entry.
- **Read.**  Every input byte's eight bits go into the dead cell, two per
  *tooth*, a short up-column of reads; an essential input's value bit is
  enqueued as it lands, and an ignored input is read and dropped.
- **Select.**  The ``j``-th essential input is dequeued into the dead cell
  and tested by a ``C`` up.  A 1 turns left onto the merge cell; a 0 runs
  ``2**(k-1-j) + 1`` ``C`` cells heading right, moving the pointer that
  far left, and comes back heading left onto the merge, a ``C`` too: the 1
  path meets it heading up on a 1 and turns left, the 0 path steps the
  pointer right onto the new dead cell.  The 0s leave the pointer
  ``2**k - 1 - row`` entries left of where it started.
- **Print.**  The answer is the dead cell's left neighbour.  A fixed chain
  of units prints it and the other seven bits of ``"0"``/``"1"``; a ``D``
  then sends the pointer around a 2x2 loop that writes nothing, where the
  interpreter halts.

Constant subtrees are not folded nor repeated ones shared: every row
shares each input's move, so a constant block still needs a cell for each
entry the pointer can land on, and sharing a repeated block needs moves
that differ by path -- the per-path drawing of the ``4**n`` tree this
replaced.  A wholly constant table is one cell and no gadget.

Five rows: the write row at the bottom, and above it a four-row band the
select gadgets fill from the right edge, reached by wrapping, under the
write row's columns.  A random table measures 1,075 cells at ``n = 6`` and
7.69 a row at ``n = 12``; the decision tree this replaced grew as
``4**n``, 9,983,952 cells at ``n = 6``.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

RIGHT, DOWN, LEFT, UP = range(4)
_STEPS = ((1, 0), (0, 1), (-1, 0), (0, -1))

#: The write row, last so the ``DDDDDD`` terminator can sit on it.
_HEIGHT = 5
_WRITE = 4
#: The band's bottom row: where a select gadget is entered, heading left.
_BASE = 3

#: Bits per input character: input arrives a byte at a time.
_BITS = 8

#: One unit per printed bit of ``"0"``/``"1"`` (``f`` then ``0001100``,
#: least significant first): the op on its right-heading cell, then the
#: ops on its left-heading cells after the print.  The pointer starts on
#: the dead cell, zeroed first; the answer ``f`` is one cell left.
_UNITS = (
    ("C", "D"),  # step onto f; print f; zero f
    ("", ""),
    ("", ""),
    ("", "C"),  # three 0s from f; step right, flipping dead to 1
    ("", ""),
    ("", "D"),  # two 1s; zero dead
    ("", ""),
    ("", ""),  # two 0s, then the loop
)


class _Grid:
    """Cells on a ``width`` x ``_HEIGHT`` torus; a crossing must be ``B``."""

    def __init__(self, width: int) -> None:
        self.width = width
        self.cells: dict[tuple[int, int], str] = {}

    def put(self, x: int, y: int, cell: str) -> None:
        key = (x % self.width, y % _HEIGHT)
        old = self.cells.get(key)
        if old is not None and (old != cell or cell != "B"):
            raise AssertionError(f"layout collision at {key}: {old} vs {cell}")
        self.cells[key] = cell

    def render(self) -> str:
        rows = [["B"] * self.width for _ in range(_HEIGHT)]
        for (x, y), cell in self.cells.items():
            rows[y][x] = cell
        return "\n".join("".join(row) for row in rows)


class _Walker:
    """Lays cells along the pointer's own path, turning at each ``A``."""

    def __init__(self, grid: _Grid, x: int, y: int, heading: int) -> None:
        self.grid, self.x, self.y, self.heading = grid, x, y, heading

    def put(self, cells: str) -> None:
        for cell in cells:
            self.grid.put(self.x, self.y, cell)
            if cell == "A":
                self.heading = (self.heading + 1) % 4
            dx, dy = _STEPS[self.heading]
            self.x += dx
            self.y += dy

    def to(self, x: int) -> None:
        """Travel straight to column ``x`` over ``B`` cells."""
        self.put("B" * abs(self.x - x))


def _tooth(w: _Walker, reads: int, *, enqueue: bool) -> None:
    """Heading left: ``reads`` up-reads, an enqueue if asked, down one row.

    The down column re-crosses the arrival row at a ``B`` the walk already
    laid, so the next tooth starts two columns on (three after an enqueue).
    """
    if enqueue:
        w.put("B")
    x = w.x
    w.put("A" + "D" * reads + "A" + "D" * enqueue + "A" + "B" * (reads + 1) + "A")
    w.to(x - 2)


def _shift(w: _Walker, rows: int) -> None:
    """Heading left: drop ``rows`` rows (1 to 3) via a loop up and over."""
    x = w.x
    w.put("AAA" + "B" * rows + "A")
    w.to(x - 2)


def _select(grid: _Grid, w: _Walker, run: int, *, last: bool) -> _Walker:
    """Heading left on ``_BASE``: test the next input, move ``run`` on a 0.

    Spans ``run + 6`` columns left of its arrival; leaves heading left on
    ``_BASE``, or on ``_BASE - 2`` for the last input.
    """
    x = w.x - run - 3  # the test column
    w.to(x + 1)
    w.put("DAC")  # dequeue the input; turn up; test it
    grid.put(x - 1, _BASE - 1, "A")  # a 1 turns left, then up
    zero = _Walker(grid, x, _BASE - 2, UP)
    zero.put("BA" + "C" * (run + 1) + "AA")
    zero.to(x - 1)
    grid.put(x - 1, _BASE - 2, "C")  # the merge
    w = _Walker(grid, x - 2, _BASE - 2, LEFT)
    if not last:
        w.put("B")
        _shift(w, 2)
    return w


def _print(grid: _Grid, w: _Walker) -> None:
    """Heading left on the dead cell: print the answer byte, then loop."""
    w.put("D")  # zero the dead cell
    for index, (right, left) in enumerate(_UNITS):
        w.to(w.x - 2)
        x = w.x
        # Up, over, and down one column on: the down column crosses the
        # arrival row at a B and prints one row below it.
        w.put("AA" + (right or "B") + "ABCA")
        if index == len(_UNITS) - 1:
            break
        # Left along the bottom, then up and back down onto the arrival
        # row two columns left of the last unit.
        w.put(left.ljust(3, "B") + "ABBAAAB")
        assert w.x == x - 3
    x, y = w.x, w.y
    grid.put(x, y, "D")  # D left: zero the cell, then the queue is empty
    for dx, dy in ((-1, 0), (-1, -1), (0, -1)):
        grid.put(x + dx, y + dy, "A")  # D down turns left forever


def _teeth(essential: set[int], n: int) -> list[tuple[int, bool]]:
    """Each tooth's read count and whether it enqueues.

    Reads go two to a tooth, and an essential input's value bit closes its
    tooth so the enqueue follows it: ``v j j | j j | j j | j v | ...``.
    An ignored input is read like any other bit and never enqueued.
    """
    teeth: list[tuple[int, bool]] = []
    pending = 0
    for index in range(_BITS * n):
        pending += 1
        value = index % _BITS == 0 and index // _BITS in essential
        if value or pending == 2:
            teeth.append((pending, value))
            pending = 0
    if pending:
        teeth.append((pending, False))
    return teeth


def _layout(table: str, n: int) -> str:
    essential = essential_inputs(table, n)
    core = read_at(table, essential, n)
    write = "".join("C" if bit == "1" else "CD" for bit in core) + "C"
    runs = [1 << (len(essential) - 1 - j) for j in range(len(essential))]
    # Select gadgets of run + 8 columns, the last 3 short, then the
    # 39-column print chain; with no gadget, the print chain alone.
    band = sum(run + 8 for run in runs) + 36 if runs else 39
    span = max(len(write), band)
    teeth = _teeth(set(essential), n)
    # The read block ends on the row the band starts on, past the wrap.
    start = _BASE if runs else _BASE - 2
    drift = (start - _WRITE - len(teeth)) % _HEIGHT
    shifts = [3] * (drift // 3) + ([drift % 3] if drift % 3 else [])
    reads = 2 + sum(3 if enqueue else 2 for _, enqueue in teeth) + 2 * len(shifts)
    # Six columns left of the read block: column 0 and the terminator's D's.
    width = span + reads + 6
    grid = _Grid(width)
    w = _Walker(grid, 0, 0, DOWN)
    w.put("B" * _WRITE + "A")  # down column 0, then left (wrapping)
    w.x %= width
    w.put(write)
    w.to(width - 1 - span)
    w.put("BB")
    for count, enqueue in teeth:
        _tooth(w, count, enqueue=enqueue)
    for rows in shifts:
        _shift(w, rows)
    w.y %= _HEIGHT
    assert (w.x, w.y) == (5, start), (w.x, w.y)
    w.to(-1)  # across column 0 and around to the right edge
    w.x %= width
    for index, run in enumerate(runs):
        w = _select(grid, w, run, last=index == len(runs) - 1)
    _print(grid, w)
    # The loop's left column stays clear of the read block.
    assert w.x - 1 >= width - span, (w.x, width - span)
    for x in range(1, 7):
        grid.put(x, _WRITE, "D")  # the terminator, off every path
    return grid.render()


def abcdirection(truth_table: str) -> str:
    """Build an ABCDirection program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    return _layout(truth_table, n)


LANGUAGE = Language(
    "ABCDirection",
    "abcdirection",
    category="grid_based",
    boolean=abcdirection,
    shape=Shape.REDUCING,
    contract=BooleanContract(input_shape="char_stream"),
    eof="EOF supplies zero bits",
    empty_program="program must contain a line with DDDDDD",
    no_wrap="a newline adds a grid row and moves every vertical path",
)
