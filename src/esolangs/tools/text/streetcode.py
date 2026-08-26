"""The Streetcode text generator.

One language, one file, as the boolean package already does for its own
Streetcode.  It earns it for the same reason LaserFuck did: at ~400 lines
it was a quarter of ``other.py``, and it is doing something none of the
neighbours do -- walling a two-lane street around its instructions,
folding that street into a boustrophedon to meet a width, and building the
first character's code point with a counting loop instead of a unary walk.

Two constructions are built and the shorter wins; see :func:`streetcode`.
"""

from esolangs.tools.wrap import shortest

__all__ = ["streetcode"]


def streetcode(text: str, width: int | None = None) -> str:
    """Build a Streetcode program that outputs ``text``.

    Printing needs no branching at all, so the program is a single
    straight street, drawn the way the wiki draws its own worked example:
    a box of ``-``/``|`` walls around two lanes, the blank northern one
    for oncoming traffic and the southern one carrying the instructions
    the car drives East along, from the ``C`` start to a closing ``;``.
    Streets are two characters wide per the spec, so the empty lane is
    not padding -- a one-lane corridor is not a street at all.  Each
    character is a run of ``^``/``~`` walking the one cell the car never
    leaves from the previous character's code point to this one's, then
    an ``O``.  CP stays at 0 throughout -- no ``=``/``_`` and no second
    cell is ever needed.

    The walls are load-bearing rather than decoration: they are what makes
    the right-hand-wall rule send the car straight down the row (the
    initial heading is derived from having a wall on the right, which is
    why the instructions occupy the southern lane), and with no
    gap-and-``+`` shape anywhere in the grid the car never meets a road
    mouth, so the ambiguous-turn and lane-merging rules the boolean
    generator has to steer around never come into play.

    The output alphabet is unrestricted: cells are unbounded signed
    integers and ``O`` prints ``chr()`` of one, so any code point works,
    including characters that are walls in the *grid* (``-``, ``|``,
    ``+``) -- they are emitted as ``^``/``~`` runs, never drawn.

    The ``^``/``~`` runs are unary, so walking to a code point costs
    ``O(delta)``.  The first character is the expensive one -- its delta
    is the whole code point, 72 for ``H`` and 937 for a Greek omega --
    and it is built with a counting loop instead: a ring the car laps
    under the control of a counter, adding a fixed amount per lap, which
    makes the value a *product* rather than a walk.  See
    :func:`_streetcode_ring`.  Later characters keep the unary walk: a
    ring costs a fixed block of rows beneath the street, and the gaps
    between adjacent code points are almost always smaller than that
    block, so walking one is cheaper than ringing it.

    ``width`` folds that street into a boustrophedon of two-lane hairpins:
    the car descends a shared two-wide corridor to the lowest pair of
    lanes, drives each pair out and back, and climbs to the pair above.
    See :func:`_streetcode_serpentine`.  A ring survives that fold -- the
    car meets it first, in the lowest lane, and the block hangs below the
    southern wall where the fold has not built anything -- so the folded
    program is also built both ways.  See
    :func:`_streetcode_ring_serpentine`.
    """
    instructions = _streetcode_instructions(text)
    if width is not None and width >= _STREETCODE_MIN_WIDTH:
        # Folding does not make the first character's walk any cheaper: it
        # packs the same unary run into more rows.  So the ring is built
        # here too, hung under the fold's southern wall where there is
        # nothing to collide with, and the shorter shape wins as ever.
        folded = _streetcode_serpentine(instructions, width)
        ringed = _streetcode_ring_serpentine(text, width) if text else None
        if ringed is None:
            return folded
        return shortest(ringed, folded)
    # Both shapes are built and the shorter one wins, rather than predicting
    # the winner from the code point: the two layouts are what they cost.
    straight = _streetcode_straight(instructions)
    ring = _streetcode_ring(text) if text else None
    if ring is None:
        return straight
    return shortest(ring, straight)


def _streetcode_instructions(text: str) -> str:
    """Build the run that walks the cell through ``text``'s code points."""
    row = ["C"]
    prev = 0
    for c in text:
        delta = ord(c) - prev
        row.append(("^" if delta >= 0 else "~") * abs(delta) + "O")
        prev = ord(c)
    row.append(";")
    return "".join(row)


def _streetcode_straight(instructions: str) -> str:
    """Wall ``instructions`` into the two-lane street the wiki draws."""
    wall = "+" + "-" * len(instructions) + "+"
    oncoming = "|" + " " * len(instructions) + "|"
    return "\n".join([wall, oncoming, f"|{instructions}|", wall])


# The counting-loop ring, generalized from the hand-written program in
# ``tests/interpreters/test_streetcode.py`` (``TestStreetcodeCountingLoop``).
# ``k`` widens the island, which lengthens the lap; the rows are otherwise
# the hand-written ones cell for cell.
_RING_ROWS = (
    "+  ++{plus}  +",
    "|      {gap}|",
    "| ^_~ {gap}=|",
    "| ^++{plus}= |",
    "|^^++{plus}^U|",
    "|^^^^^{up}=|",
    "|^^^^^^{up}|",
    "+------{dash}+",
)

# The hand-written ring's nine entry ``^`` and eight lap ``^`` are the
# factors it happens to use, not minimums: blanking either run shortens
# that factor, so a ring makes any ``counter * per_lap``.  Both runs live
# inside the fixed block below, which is what a ring costs.
_RING_COUNTER_CELLS = 9
_RING_LAP_CELLS = 8


def _ring_rows(k: int, counter: int, per_lap: int) -> list[str]:
    """Draw the ring block widened by ``k``, with its factor runs trimmed.

    ``counter`` of the entry ``^`` and ``per_lap`` of the lap ``^`` are
    kept and the rest blanked, which is what sets the two factors.  The
    cells are listed in the order the car drives them, so trimming from
    the end of each list leaves a contiguous run.
    """
    rows = [
        row.format(plus="+" * k, gap=" " * k, up="^" * k, dash="-" * k)
        for row in _RING_ROWS
    ]
    grid = [list(row) for row in rows]
    # Entry ``^`` in drive order (block-relative): the descent, then the
    # run East along the ring's southern lane.  The street cell above the
    # block is the ninth and is drawn by the caller.
    entry = [(4, 1), (5, 1), (6, 1)] + [(6, c) for c in range(2, 7 + k)]
    # Lap ``^`` in drive order, starting just after the ``U``.
    lap = (
        [(4, 5 + k), (5, 5 + k)]
        + [(5, c) for c in range(4 + k, 1, -1)]
        + [(4, 2), (3, 2), (2, 2)]
    )
    # ``counter`` includes the street cell the caller draws, so the block
    # holds one fewer.
    for cells, keep in ((entry, counter - 1), (lap, per_lap)):
        for i, (r, c) in enumerate(cells):
            if grid[r][c] == "^" and i >= keep:
                grid[r][c] = " "
    return ["".join(row) for row in grid]


def _plan_ring(target: int) -> tuple[int, int, int, int] | None:
    """Cheapest ``(k, counter, per_lap, remainder)`` building ``target``.

    The lap adds ``per_lap`` to the accumulator ``counter`` times, so the
    ring makes their product and the remainder is walked on the street
    afterwards, where CP already points at the accumulator.  ``k`` widens
    the island when a factor needs more cells than the hand-written block
    has.  Cost is the street width the choice occupies; the block's rows
    are fixed, so a wider island and a longer remainder are what vary.
    """
    best: tuple[int, int, int, int, int] | None = None
    for k in range(_RING_K_LIMIT):
        counter_cells = _RING_COUNTER_CELLS + k
        lap_cells = _RING_LAP_CELLS + k
        for per_lap in range(1, lap_cells + 1):
            counter = min(counter_cells, target // per_lap)
            for c in (counter, counter + 1):
                if not 1 <= c <= counter_cells:
                    continue
                remainder = target - c * per_lap
                if remainder < 0:
                    continue
                cost = 8 + k + remainder
                if best is None or cost < best[0]:
                    best = (cost, k, c, per_lap, remainder)
    if best is None:
        return None
    return best[1], best[2], best[3], best[4]


# Enough to cover any code point worth ringing: the factors wanted are
# near ``sqrt(target)``, so a modest island covers the byte range and up.
_RING_K_LIMIT = 32


def _streetcode_ring(text: str) -> str | None:
    """Build ``text`` with a counting loop for its first character.

    The hand-written counting loop in the interpreter tests
    (``TestStreetcodeCountingLoop``) laps an island nine times adding
    eight per lap, making the 72 that prints ``H``.  Its nine and eight
    are just the ``^`` it draws: blanking cells shortens a factor and
    widening the island lengthens one, so the ring makes any
    ``counter * per_lap``, and a remainder walked on the street afterwards
    covers what the product misses.  That turns the first character's
    delta -- its whole code point, 937 for a Greek omega -- from a unary
    walk into a product.

    Only the first character is worth this.  Later deltas are the gaps
    between adjacent characters, and a ring's block of rows costs more
    than walking a gap that small, so they keep the straight corridor of
    increments.  Returns ``None`` only when no ring plan exists at all;
    whether a ring that *does* exist is worth emitting is the caller's
    call, made by comparing the two finished programs.

    The rows below the street are right-trimmed: nothing east of the ring
    block is drivable, so those trailing spaces are padding rather than
    road, and keeping them would cost more than the ring saves.
    """
    first = ord(text[0])
    plan = _plan_ring(first)
    if plan is None:
        return None
    k, counter, per_lap, remainder = plan
    block = _ring_rows(k, counter, per_lap)
    block_width = len(block[0])

    tail = []
    prev = first
    for char in text[1:]:
        delta = ord(char) - prev
        tail.append(("^" if delta >= 0 else "~") * abs(delta) + "O")
        prev = ord(char)
    after = "^" * remainder + "O" + "".join(tail) + ";"

    left = 3
    width = left + block_width + len(after) + 1
    grid = [[" "] * width for _ in range(3 + len(block))]
    grid[0] = list("+" + "-" * (width - 2) + "+")
    for r in (1, 2):
        grid[r][0] = grid[r][width - 1] = "|"
    # The street's southern wall is solid apart from the ring's own gaps,
    # so it is drawn first and the block stamped over it.
    grid[3] = list("+" + "-" * (width - 2) + "+")
    for r, block_row in enumerate(block):
        for c, cell in enumerate(block_row):
            grid[3 + r][left + c] = cell

    grid[2][1] = "C"
    grid[2][2] = "^"  # the counter's first cell, above the descent
    for i, cell in enumerate(after):
        grid[2][left + block_width + i] = cell

    return "\n".join("".join(row).rstrip() for row in grid)


# A fold needs two wall columns, the two-cell vertical corridor the car
# descends and climbs, and at least one lane column beside it; below this
# there is nowhere to turn and the straight street is emitted instead.
_STREETCODE_MIN_WIDTH = 5


def _streetcode_serpentine(instructions: str, width: int) -> str:
    """Fold ``instructions`` into a boustrophedon street ``width`` wide.

    Each fold is a two-lane street, per the spec's "two characters wide":
    a pair of rows the car drives around as one hairpin, out along the
    lane with the wall on its right and back along the other.  Driving
    East the wall on the right is the one *below*, so the eastbound lane
    is the lower row of the pair and the westbound lane the upper; the
    car therefore runs East along the bottom of a pair, turns at the end
    wall, comes back West along the top, and drops through a gap into the
    next pair.  That keeps the whole path a plain wall-hugging circuit:
    no gap-and-``+`` shape is drawn, so no junction, ambiguous-turn, or
    lane-merge rule ever fires.

    The vertical corridor joining the pairs is two cells wide for the same
    reason the lane pairs are two rows deep: "two characters wide" is a
    rule about every street in the grid, not just the horizontal ones, and
    a one-cell corridor is not a street the car may legally drive.  An
    earlier fold made that corridor a single column; it round-tripped --
    the interpreter drove it without complaint -- but the grid it drew was
    not a legal street plan.

    The instructions are laid along the car's path in the order it drives
    them, so the returning lane is written to the grid reversed.  The
    closing ``;`` lands at the path's end, which is what stops the car: a
    street with no halt is a dead end, and the right-hand hug bounces the
    car back along it, re-executing every cell it already ran.
    """
    cells = list(instructions)
    # Column 0 is the left wall, columns 1 and 2 the shared two-wide
    # vertical corridor the car descends and climbs, and the last column
    # the right wall; the lanes run between.
    lanes = width - 4
    pairs = -(-len(cells) // (2 * lanes))

    grid: list[list[str]] = [["+"] + ["-"] * (width - 2) + ["+"]]
    for n in range(pairs):
        for _ in range(2):
            grid.append(["|"] + [" "] * (width - 2) + ["|"])
        if n < pairs - 1:
            divider = ["+"] + ["-"] * (width - 2) + ["+"]
            # the descent gap, spanning the whole two-wide corridor
            divider[1] = divider[2] = " "
            grid.append(divider)
    grid.append(["+"] + ["-"] * (width - 2) + ["+"])

    # The car descends column 1 to the *lowest* pair, drives its hairpin,
    # then climbs back through each gap to the pair above, so the pairs
    # are filled bottom-up.  Within a pair it runs East along the lower
    # lane (wall below on its right), turns at the end wall, and returns
    # West along the upper lane, ending back at the corridor.
    path: list[tuple[int, int]] = []
    for n in range(pairs - 1, -1, -1):
        top = 1 + n * 3
        bottom = top + 1
        path += [(bottom, c) for c in range(3, width - 1)]
        path += [(top, c) for c in range(width - 2, 2, -1)]

    for (r, c), instruction in zip(path, cells, strict=False):
        grid[r][c] = instruction
    return "\n".join("".join(row) for row in grid)


def _streetcode_ring_serpentine(text: str, width: int) -> str | None:
    """Fold ``text`` with a counting loop for its first character.

    The straight ring (:func:`_streetcode_ring`) and the fold
    (:func:`_streetcode_serpentine`) compose because the car meets the
    ring first and the block hangs where the fold builds nothing.  The
    serpentine fills its lane pairs bottom-up and starts the car in the
    lowest eastbound lane, which is exactly where a ring prefix has to
    go: the ``C``, the cells over the block, and the remainder walk take
    the head of that lane, and the tail's characters carry on from there
    through the ordinary boustrophedon.

    The block itself is stamped below the grid's southern wall, so it
    collides with nothing, and the gaps it needs are cut into that wall
    rather than into a fold divider.  Those gaps are why the wall is
    drawn before the block is stamped over it, as in the straight ring.

    Returns ``None`` when the prefix will not fit one lane -- a wide
    island or a long remainder can outrun ``width``, and ``中文``'s plan
    wants a remainder of 18453 -- in which case the caller keeps the
    plain fold.  The ring is not re-planned to suit the width: what a
    ring costs is what it costs, and the two finished programs are
    compared as they are.
    """
    plan = _plan_ring(ord(text[0]))
    if plan is None:
        return None
    k, counter, per_lap, remainder = plan
    block = _ring_rows(k, counter, per_lap)
    block_width = len(block[0])

    # Lanes run from column 3 to the right wall; the prefix occupies the
    # head of the lowest one.  ``C`` sits above the block's descent, so
    # the block is stamped from the ``C`` column onward.
    left = 3
    prefix = "C^" + " " * (block_width - 2) + "^" * remainder + "O"
    # One lane cell must remain for the tail to start on, plus the right
    # wall; without it the prefix has nowhere to hand over.
    if left + len(prefix) + 1 > width - 1:
        return None

    tail = []
    prev = ord(text[0])
    for char in text[1:]:
        delta = ord(char) - prev
        tail.append(("^" if delta >= 0 else "~") * abs(delta) + "O")
        prev = ord(char)
    cells = list("".join(tail) + ";")

    lanes = width - 4
    # The lowest pair holds one full westbound lane plus whatever the
    # prefix leaves of its eastbound one; every pair above holds two.
    first_pair = (lanes - len(prefix)) + lanes
    rest = max(0, len(cells) - first_pair)
    pairs = 1 + -(-rest // (2 * lanes))

    grid: list[list[str]] = [["+"] + ["-"] * (width - 2) + ["+"]]
    for n in range(pairs):
        for _ in range(2):
            grid.append(["|"] + [" "] * (width - 2) + ["|"])
        if n < pairs - 1:
            divider = ["+"] + ["-"] * (width - 2) + ["+"]
            divider[1] = divider[2] = " "
            grid.append(divider)
    grid.append(["+"] + ["-"] * (width - 2) + ["+"])

    # The car's path, as in the plain fold, except the lowest eastbound
    # lane starts after the prefix that lane already carries.
    path: list[tuple[int, int]] = []
    for n in range(pairs - 1, -1, -1):
        top = 1 + n * 3
        bottom = top + 1
        start = left + len(prefix) if n == pairs - 1 else left
        path += [(bottom, c) for c in range(start, width - 1)]
        path += [(top, c) for c in range(width - 2, left - 1, -1)]

    if len(cells) > len(path):
        return None

    bottom_row = 1 + (pairs - 1) * 3 + 1
    for i, cell in enumerate(prefix):
        grid[bottom_row][left + i] = cell
    for (r, c), instruction in zip(path, cells, strict=False):
        grid[r][c] = instruction

    # The southern wall is already drawn; stamp the block over it so its
    # gaps land in the wall, then hang the remaining rows below.
    rows = ["".join(row) for row in grid]
    wall = list(rows[-1])
    for c, ch in enumerate(block[0]):
        wall[left + c] = ch
    rows[-1] = "".join(wall)
    rows += [" " * left + row for row in block[1:]]
    return "\n".join(row.rstrip() for row in rows)
