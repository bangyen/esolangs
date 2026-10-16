"""ABCDirection Boolean program generator: the table on the tape.

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

Five rows: the write row at the bottom, and above it a four-row band the
select gadgets fill from the right edge, reached by wrapping, under the
write row's columns.  A wholly constant table is one cell and no gadget.

``balance=True`` winds the one leftward walk into a helix.  The write
chain, the reads and the band each fill a slab of rows (2, 5 and 4 a lap, so
a drop has room above it) and drop to the next lap where a ``B`` precedes a
2x2 up-and-over; a lap stays under the width, so it never meets its own
landing.  Teeth alternate ``rise`` and plain to stay in five rows without
wrapping.  The width is the squarest the arithmetic lap count allows, from
the widest atom (a gadget, ``run + 8``) to the flat width; the flat layout
stays a candidate.  ``n = 2``: 83x5 flat, 33x16 balanced.

Size:
    O(T) cells, 7.69 a row at ``n = 12``; n=6 random 1847: 1,079 chars,
    n=10 random 1847: 8,199 chars (1,075 cells at ``n = 6``).

Decisions:
    Constant subtrees are not folded nor repeated ones shared: every row
    shares each input's move, so a constant block still needs a cell for each
    entry the pointer can land on, and sharing a repeated block needs moves
    that differ by path -- the per-path drawing of the ``4**n`` tree this
    replaced (9,983,952 cells at ``n = 6``).
"""

from typing import NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.token_balance import rendered_side
from esolangs.generation.wrap import balance_score
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
    """Cells on a ``width`` x ``height`` torus; a crossing must be ``B``."""

    def __init__(self, width: int, height: int = _HEIGHT) -> None:
        self.width = width
        self.height = height
        self.cells: dict[tuple[int, int], str] = {}

    def put(self, x: int, y: int, cell: str) -> None:
        key = (x % self.width, y % self.height)
        old = self.cells.get(key)
        if old is not None and (old != cell or cell != "B"):
            raise AssertionError(f"layout collision at {key}: {old} vs {cell}")
        self.cells[key] = cell

    def render(self) -> str:
        rows = [["B"] * self.width for _ in range(self.height)]
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


def _tooth(w: _Walker, reads: int, *, enqueue: bool, rise: bool = False) -> None:
    """Heading left: ``reads`` up-reads, an enqueue if asked, down one row.

    The down column re-crosses the arrival row at a ``B`` the walk already
    laid, so the next tooth starts two columns on (three after an enqueue).
    ``rise`` pads the up column by a ``B`` and shortens the down one, so the
    tooth ends one row *up*; alternating the two keeps a run of teeth in five
    rows without wrapping.
    """
    if enqueue:
        w.put("B")
    x = w.x
    if rise:
        w.put("AB" + "D" * reads + "A" + "D" * enqueue + "A" + "B" * reads + "A")
    else:
        w.put("A" + "D" * reads + "A" + "D" * enqueue + "A" + "B" * (reads + 1) + "A")
    w.to(x - 2)


def _shift(w: _Walker, rows: int) -> None:
    """Heading left: drop ``rows`` rows (1 to 3) via a loop up and over."""
    x = w.x
    w.put("AAA" + "B" * rows + "A")
    w.to(x - 2)


def _select(
    grid: _Grid, w: _Walker, run: int, *, last: bool, base: int = _BASE
) -> _Walker:
    """Heading left on ``base``: test the next input, move ``run`` on a 0.

    Spans ``run + 6`` columns left of its arrival; leaves heading left on
    ``base``, or on ``base - 2`` for the last input.
    """
    x = w.x - run - 3  # the test column
    w.to(x + 1)
    w.put("DAC")  # dequeue the input; turn up; test it
    grid.put(x - 1, base - 1, "A")  # a 1 turns left, then up
    zero = _Walker(grid, x, base - 2, UP)
    zero.put("BA" + "C" * (run + 1) + "AA")
    zero.to(x - 1)
    grid.put(x - 1, base - 2, "C")  # the merge
    w = _Walker(grid, x - 2, base - 2, LEFT)
    if not last:
        w.put("B")
        _shift(w, 2)
    return w


def _print_unit(grid: _Grid, w: _Walker, index: int) -> None:
    """Heading left past two ``B``: print unit ``index``; the last also loops.

    Each unit ends with the next one's two ``B``, where a lap may drop.
    """
    right, left = _UNITS[index]
    x = w.x
    # Up, over, and down one column on: the down column crosses the
    # arrival row at a B and prints one row below it.
    w.put("AA" + (right or "B") + "ABCA")
    if index < len(_UNITS) - 1:
        # Left along the bottom, then up and back down onto the arrival
        # row two columns left of the last unit.
        w.put(left.ljust(3, "B") + "ABBAAAB")
        assert w.x == x - 3
        w.to(w.x - 2)
        return
    x, y = w.x, w.y
    grid.put(x, y, "D")  # D left: zero the cell, then the queue is empty
    for dx, dy in ((-1, 0), (-1, -1), (0, -1)):
        grid.put(x + dx, y + dy, "A")  # D down turns left forever


def _print(grid: _Grid, w: _Walker) -> None:
    """Heading left on the dead cell: print the answer byte, then loop."""
    w.put("D")  # zero the dead cell
    w.to(w.x - 2)
    for index in range(len(_UNITS)):
        _print_unit(grid, w, index)


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


#: Columns a select gadget spans, and the print units: the first with the
#: zeroing ``D``, the middle, the last.
_GADGET = 8
_PRINT_SIZES = (8, 5, 5, 5, 5, 5, 5, 1)


class _Plan(NamedTuple):
    """The three phases cut into laps of at most ``width`` columns."""

    write: list[str]
    reads: list[list[tuple[int, bool]]]
    #: ``(kind, arg)``: ``gadget`` and ``last`` carry a run; ``print`` an index.
    band: list[list[tuple[str, int]]]

    @property
    def height(self) -> int:
        """Two rows a write lap, five a reads lap, four a band lap, one spare."""
        return 2 * len(self.write) + 5 * len(self.reads) + 4 * len(self.band) + 1


def _laps(sizes: list[int], room: int) -> list[list[int]]:
    """Greedy cut of ``sizes`` into laps of total at most ``room``; indices."""
    laps: list[list[int]] = [[]]
    used = 0
    for index, size in enumerate(sizes):
        if used + size > room and laps[-1]:
            laps.append([])
            used = 0
        laps[-1].append(index)
        used += size
    return laps


def _pieces(runs: list[int]) -> list[tuple[str, int]]:
    """The band's atoms in order: gadgets, the last with print unit 0, the rest."""
    gadgets = [("gadget", run) for run in runs[:-1]]
    head = ("last", runs[-1]) if runs else ("first", 0)
    return [*gadgets, head, *(("print", i) for i in range(1, len(_UNITS)))]


def _piece_size(kind: str, arg: int) -> int:
    """Columns a band atom spans: a gadget's last three are the print's."""
    if kind == "gadget":
        return arg + _GADGET
    if kind == "last":
        return arg + _GADGET - 3 + _PRINT_SIZES[0]
    return _PRINT_SIZES[arg if kind == "print" else 0]


def _sizes(
    table: str, n: int
) -> tuple[str, list[tuple[int, bool]], list[tuple[str, int]]]:
    """The write chain, the teeth, the band's atoms."""
    essential = essential_inputs(table, n)
    write = "".join("C" if bit == "1" else "CD" for bit in read_at(table, essential, n))
    runs = [1 << (len(essential) - 1 - j) for j in range(len(essential))]
    return write + "C", _teeth(set(essential), n), _pieces(runs)


def _floor(table: str, n: int) -> int:
    """The least width: the widest atom plus its lap's cost, and room for ``DDDDDD``."""
    return max(14, *(_piece_size(*piece) + 4 for piece in _sizes(table, n)[2]))


def _height(table: str, n: int, width: int) -> int:
    """Rows of the helix at ``width``: two a write lap, five a reads, four a band."""
    write, teeth, pieces = _sizes(table, n)
    room = width - 4
    return (
        2 * -(-len(write) // (room - 1))
        + 5 * len(_laps([3 if enqueue else 2 for _, enqueue in teeth], room))
        + 4 * len(_laps([_piece_size(*piece) for piece in pieces], room))
        + 1
    )


def _plan(table: str, n: int, width: int) -> _Plan:
    write, teeth, pieces = _sizes(table, n)
    # Each lap spends two columns landing and one on its drop; a write lap
    # also ends on a ``B``.
    room = width - 4
    chunk = room - 1
    return _Plan(
        [write[i : i + chunk] for i in range(0, len(write), chunk)],
        [
            [teeth[i] for i in lap]
            for lap in _laps([3 if enqueue else 2 for _, enqueue in teeth], room)
        ],
        [
            [pieces[i] for i in lap]
            for lap in _laps([_piece_size(*piece) for piece in pieces], room)
        ],
    )


def _helix(table: str, n: int, width: int) -> str:
    plan = _plan(table, n, width)
    grid = _Grid(width, plan.height)
    w = _Walker(grid, 0, 0, DOWN)
    w.put("ABB")  # the corner, then the two landing columns every lap opens with
    first = None
    # Write laps sit on every other row so each drop's up-and-over has room.
    reads_at = 2 * len(plan.write) - 1
    for index, chunk in enumerate(plan.write):
        w.put(chunk + "B")
        if first is None:
            first = w.x
        last = index == len(plan.write) - 1
        _shift(w, reads_at + 3 - w.y if last else 2)
    band_at = reads_at + 5 * len(plan.reads)
    start = (
        _BASE
        if plan.band[0][0][0] == "gadget" or plan.band[0][0][0] == "last"
        else _BASE - 2
    )
    for index, lap in enumerate(plan.reads):
        for tooth, (count, enqueue) in enumerate(lap):
            _tooth(w, count, enqueue=enqueue, rise=tooth % 2 == 1)
        last = index == len(plan.reads) - 1
        top = reads_at + 5 * (index + 1)
        _shift(w, (band_at + start if last else top + 3) - w.y)
    for index, pieces in enumerate(plan.band):
        base = band_at + 4 * index + _BASE
        for position, (kind, arg) in enumerate(pieces):
            if position == 0 and index > 0:
                _shift(w, 4)
            if kind == "print":
                _print_unit(grid, w, arg)
                continue
            if kind != "first":
                w = _select(grid, w, arg, last=kind == "last", base=base)
            if kind == "gadget":
                continue
            w.put("D")  # zero the dead cell
            w.to(w.x - 2)
            _print_unit(grid, w, 0)
    assert first is not None
    # The spare row is crossed only by the first drop's up-and-over.
    left = first % width
    gap = 0 if 6 <= left < width - 1 else 2 if left == width - 1 else left + 2
    for x in range(gap, gap + 6):
        grid.put(x, plan.height - 1, "D")
    return grid.render()


def _balance(table: str, default: str) -> str:
    """The squarest of the flat layout and the helix at its best width."""
    n = _validate_truth_table(table)
    flat = len(default.split("\n")[0])

    def score(width: int) -> tuple[int, int, int]:
        height = _height(table, n, width)
        return rendered_side(width, height), width * height + height - 1, width

    width = min(range(_floor(table, n), flat), key=score, default=flat)
    return min(default, _helix(table, n, width), key=balance_score)


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
    balance=_balance,
    contract=BooleanContract(input_shape="char_stream"),
    eof="EOF supplies zero bits",
    empty_program="program must contain a line with DDDDDD",
    no_wrap="a newline adds a grid row and moves every vertical path",
)
