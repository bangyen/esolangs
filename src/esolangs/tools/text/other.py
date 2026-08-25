"""Other text generators."""

import math
import re
from collections import Counter, deque
from functools import cache

from esolangs.tools import laserfuck_layout
from esolangs.tools.text.helpers import (
    _factor_triple,
    _ilog,
    _literal_chunks,
    _require_ascii,
    _require_bytes,
)
from esolangs.tools.ztoalc_starts import ANCHORS

__all__ = [
    "basicfuck",
    "between",
    "bit_tilde",
    "clockwise",
    "container",
    "dimensional",
    "forbin",
    "forth",
    "home_row",
    "laserfuck",
    "myscript",
    "nevermind",
    "nocomment",
    "one_two_three",
    "painfuck",
    "pct_squared_minus_one",
    "sbleq",
    "streetcode",
    "suptiftam",
    "three_x",
    "unsquare",
    "ztoalc_l",
]


def between(text: str) -> str:
    """Generate a Between program that outputs ``text``.

    One ``p`` prints the whole text as a string literal, then ``x`` exits.
    Apostrophes are doubled (``''``) so they can appear inside the literal;
    a line break cannot because each instruction occupies one line.
    """
    # Programs are split with str.splitlines(), which treats more than \n and
    # \r as line boundaries; any of these would cut the literal in two.
    if any(c in _SPLITLINES for c in text):
        raise ValueError(
            "Between cannot output a newline or other line break "
            "(instructions are one line)"
        )
    return f"'{text.replace(chr(39), chr(39) * 2)}'p.\n.x."


# Characters str.splitlines() treats as line boundaries.
_SPLITLINES = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"


def clockwise(text: str, width: int | None = None) -> str:
    """Build a 1D parity program wrapped around a rectangle's perimeter.

    The turtle walks the ring clockwise, executing one instruction per cell.
    Three corner ``R`` cells turn it, and the final cell walks it back to the
    origin facing right, where it halts.  Each ``;`` outputs ``acc % 2``, so
    ``+`` is emitted only when the accumulator's parity needs to flip.

    Two layouts are built and the shorter one wins.  The bare *ring* keeps
    code on the perimeter only and leaves the interior dead, so a program of
    ``c`` cells costs a square of side about ``c / 4`` -- a long text is
    better than 97% blank.  The *weave* (:func:`_clockwise_weave`)
    serpentines through the interior instead and runs over 90% code, so it
    wins on everything but the shortest texts, where the ring's smaller
    fixed cost still tells.

    ``width`` bounds the columns of whichever layout is chosen.
    """
    _require_ascii(text, "Clockwise")
    prog = ""
    parity = 0
    for c in text:
        for bit in f"{ord(c):07b}":
            if parity != int(bit):
                prog += "+"
                parity = int(bit)
            prog += ";"

    if not prog:
        return ""

    folded = _clockwise_weave(prog, width)
    ring = _clockwise_ring(prog, width)
    if folded is not None:
        return min((folded, ring), key=len)
    return ring


def _clockwise_ring(prog: str, width: int | None) -> str:
    """Wrap ``prog`` around a rectangle's perimeter, the interior left dead."""
    height, width_ = _clockwise_shape(len(prog), width)
    # The three turning corners are overwritten with ``R`` below, so the
    # ring skips them rather than placing code that would be clobbered.
    # Only the top-left corner carries an instruction (the origin).
    ring = [(i, 0) for i in range(width_ - 1)]  # top row, up to the corner
    ring += [(width_ - 1, y) for y in range(1, height - 1)]  # right, inside
    ring += [(i, height - 1) for i in range(width_ - 2, 0, -1)]  # bottom back
    ring += [(0, y) for y in range(height - 2, 0, -1)]  # left column, up

    grid = [[" "] * width_ for _ in range(height)]
    for (x, y), ch in zip(ring, prog, strict=False):
        grid[y][x] = ch
    grid[0][width_ - 1] = "R"  # top-right
    grid[height - 1][width_ - 1] = "R"  # bottom-right
    grid[height - 1][0] = "R"  # bottom-left

    return "\n".join("".join(row) for row in grid)


# A weave's turning cells: the hairpin ladder in column 1, the two descent
# lanes on the right, and the corners.  Everything else is a slot.
_WEAVE_LANES = "0110"

# The narrowest weave: the home lane, the hairpin ladder, one body cell, and
# the two descent lanes.
_WEAVE_MIN_WIDTH = 5


def _weave_template(units: int, body: int) -> list[list[str]]:
    """Lay out an empty weave: ``R`` turns placed, every other cell a hole.

    ``units`` counts four-row weave groups (the walk only closes on a
    multiple of four interior rows) and ``body`` is the instruction span of
    an interior row.  Row 0 runs east, then each interior row is reached in
    the order 0, 2, 1, 4, 3, ... -- a westward row, a hairpin up into the
    row above it, and a drop past that row to the next westward one.  The
    drops overlap vertically, so the right-hand turns alternate between the
    two descent lanes on the ``0110`` cycle in :data:`_WEAVE_LANES`.
    """
    lanes = [int(bit) for bit in _WEAVE_LANES * units]
    size = body + 4
    grid = [[" "] * size for _ in range(len(lanes) + 2)]
    grid[0][size - 1] = "R"
    for row, lane in enumerate(lanes, start=1):
        grid[row][1] = "R"
        grid[row][size - 2 + lane] = "R"
    grid[-1][0] = "R"
    grid[-1][size - 1] = "R"
    return grid


def _weave_slots(grid: list[list[str]]) -> list[tuple[int, int]] | None:
    """Return the cells a walk over ``grid`` runs exactly once, in path order.

    The pointer is run over the bare template with every hole left blank, so
    the walk is the template's own geometry.  A cell it enters twice would
    run its instruction twice -- a repeated ``;`` emits a duplicate parity
    bit -- so only the single-visit cells can hold code; the rest stay blank
    and serve as the lanes the walk crosses.  Returns ``None`` when the
    template does not close (the walk leaves the grid or never returns to
    the origin), which is how a bad ``units``/``body`` pair is rejected.
    """
    from esolangs.interpreters.grid_based.clockwise import _Machine
    from esolangs.interpreters.io import IO

    rows = ["".join(row) for row in grid]
    machine = _Machine(rows, IO())
    order: list[tuple[int, int]] = []
    limit = 8 * len(rows) * len(rows[0]) + 64
    for _ in range(limit):
        if machine.halted:
            break
        cell = (machine.x, machine.y)
        try:
            machine.step()
        except ValueError:
            return None  # walked off the grid: the template is not closed
        order.append(cell)
    else:
        return None  # never came home
    seen = Counter(order)
    return [cell for cell in order if seen[cell] == 1 and grid[cell[1]][cell[0]] == " "]


def _clockwise_weave(prog: str, width: int | None) -> str | None:
    """Fold ``prog`` into a woven grid rather than a bare perimeter.

    The perimeter ring spends its whole interior on nothing, so a program of
    ``c`` cells costs a square of side ``c / 4``.  The weave walks the
    interior instead: the pointer serpentines down the grid, and because a
    turn is always clockwise it cannot simply reverse at the end of a row --
    it takes the row *two* below, then hairpins back up into the one it
    skipped.  Two descent lanes on the right and a hairpin ladder in column
    1 carry it, and the homeward lane in column 0 brings it back to the
    origin; every cell any of those lanes crosses only once still holds an
    instruction, so the grid runs better than 90% code.

    Returns ``None`` when no weave fits within ``width``, leaving the caller
    with the ring.
    """
    best: str | None = None
    limit = width if width is not None else len(prog) + _WEAVE_MIN_WIDTH
    if limit < _WEAVE_MIN_WIDTH:
        return None
    for body in range(1, limit - 3):
        units = 1
        while True:
            grid = _weave_template(units, body)
            slots = _weave_slots(grid)
            if slots is None:
                break
            if len(slots) >= len(prog):
                filled = [row[:] for row in grid]
                for (x, y), instruction in zip(slots, prog, strict=False):
                    filled[y][x] = instruction
                drawn = "\n".join("".join(row).rstrip() for row in filled)
                if best is None or len(drawn) < len(best):
                    best = drawn
                break
            units += 1
            if units > len(prog):
                break
    return best


def _clockwise_shape(cells: int, width: int | None) -> tuple[int, int]:
    """Return the ``(height, width)`` of the ring holding ``cells`` commands.

    An ``h`` x ``w`` perimeter has ``2(h + w) - 4`` cells, but three of them
    are the turning corners, so a ring carries ``2(h + w) - 7`` instructions
    and needs ``h + w >= (cells + 7) / 2``.  Splitting that sum evenly gives
    the square, which minimizes ``max(h, w)``; ``width`` caps ``w`` and moves
    the remainder onto ``h``.  Both dimensions are at least 3, the smallest
    ring with an interior.
    """
    half = -(-(cells + 7) // 2)  # ceil, the required h + w
    side = max(3, -(-half // 2))  # ceil, the square's side
    if width is None or side <= width:
        return side, side
    capped = max(3, width)
    return max(3, half - capped), capped


def container(text: str) -> str:
    """Build a Container program that outputs ``text``.

    The program encodes each character as a signed delta from the previous
    one.  Rules ``A>=i`` and ``A>=i+1`` split the delta: a positive difference
    is built by ``+d`` then the two half-rules fire in sequence, and a
    negative one symmetrically, so each character prints through the ``OUT``
    rule once the accumulator crosses it.
    """
    _require_ascii(text, "Container")
    ind = last = 0
    if text:
        res = "A:\n+1 EXIT>=1\n\nPRINT:\n+1 PRINT<=0\n-1 PRINT>=1\n\nOUT:\n"
    else:
        return "EXIT=1:\n-1 EXIT>=0"

    for c in text:
        if (o := ord(c) - last) >= 0:
            res += f"+{o} A>={ind}\n-{o} A>={ind + 1}\n"
        else:
            res += f"-{-o} A>={ind}\n+{-o} A>={ind + 1}\n"
        last = ord(c)
        ind += 2

    res += f"EXIT=1:\n-1 A>={ind - 2}"

    return res


def nevermind(text: str) -> str:
    """Build a program whose ``print`` joins its arguments without a separator.

    Commas separate arguments, so a comma in the text is encoded as ``*44``,
    which the interpreter expands back; a literal ``*44`` is split across two
    arguments so the interpreter cannot mistake it for a comma.  Line breaks
    would split the program into lines and a leading ``$`` would be read as a
    variable, so both are rejected.
    """
    if any(c in "\n\r\v\f\x1c\x1d\x1e\x85" for c in text) or text.startswith("$"):
        raise ValueError("nevermind can only print a single line without a leading $")

    args = []
    buf = ""
    i = 0
    while i < len(text):
        if text.startswith("*44", i):
            args.append(buf + "*4")
            buf = "4"
            i += 3
        elif text[i] == ",":
            buf += "*44"
            i += 1
        else:
            buf += text[i]
            i += 1
    args.append(buf)
    args = [a for a in args if a]

    return "print," + ",".join(args)


def _anchor_for(n: int) -> int:
    """Collatz start covering a text of length ``n``.

    The committed ``ANCHORS`` table maps length intervals to the record-holder
    with the smallest trajectory peak for every length in the interval, so a
    length is a plain lookup (no search).
    """
    for end, start in ANCHORS:
        if end >= n:
            return start
    raise ValueError(
        f"no Collatz start with a trajectory of {n} steps "
        f"(the longest committed record reaches {ANCHORS[-1][0]})",
    )


def ztoalc_l(text: str) -> str:
    """Build a ZTOALC L program that outputs ``text``.

    The interpreter runs lines in Collatz-trajectory order from the initial
    value on line 1, so each character is placed on the line its trajectory
    step visits.  A ``start`` whose trajectory has at least ``len(text)``
    steps is taken from the committed anchor table (covering lengths up to
    the longest known record), and the program is ``start`` on line 1 plus a
    ``print <code>`` on each visited line.
    """
    n = len(text)
    if not text:
        return "2"

    start = _anchor_for(n)
    values = _collatz_prefix(start, n)
    size = max(values)

    lines = [""] * size
    lines[0] = str(start)

    for value, char in zip(values, text, strict=False):
        lines[value - 1] = f"print {ord(char)}"

    return "\n".join(lines)


def _collatz_prefix(start: int, n: int) -> list[int]:
    values: list[int] = []
    value = start
    for _ in range(n):
        values.append(value)
        value = value // 2 if value % 2 == 0 else 3 * value + 1
    return values


def forth(text: str) -> str:
    """Each character is built as ``m * 15**n + p`` and printed with ``.``.

    ``F`` pushes 15 (the largest digit), ``*`` and ``+`` do arithmetic, and
    ``.`` prints the top of the stack as a character.  Characters are pushed
    in reverse and a ``[.]`` loop prints them, stopping at the seed 0; a NUL
    would stop that loop, so text containing one is printed with an explicit
    ``.`` per character instead.
    """
    _require_bytes(text, "Forþ")
    s = "0123456789ABCDEF"

    def build(c: str) -> str:
        o = ord(c)
        if o == 0:
            return "0"
        # base-15 digits, most significant first, folded by Horner's rule
        ds: list[int] = []
        v = o
        while v:
            ds.append(v % 15)
            v //= 15
        ds.reverse()
        prog = s[ds[0]]
        for d in ds[1:]:
            prog += "F*" + s[d] + "+"
        return prog

    if "\x00" in text:
        return "0" + "".join(build(c) + "." for c in text)
    return "0" + "".join(build(c) for c in text[::-1]) + "[.]"


def _laserfuck_linear(run: str, width: int | None) -> str:
    r"""Emit the linear LaserFuck program for ``run``, folded to ``width``.

    The linear form is the whole program on one row -- the ``\xff`` output
    mode byte, ``}}`` to face the beam right, then one ``+`` per unit of
    every byte -- above the ``|o^`` / ``_`` funnel that catches whichever
    heading the laser starts with.  It is the widest thing either generator
    emits: nineteen characters of text come to 1833 columns.

    With a width the run is folded into a zigzag instead
    (:func:`~esolangs.tools.laserfuck_layout.fold`), which costs rows rather
    than columns.  The funnel stays where it is, on the two rows below the
    first, and the fold returns to a margin clear of it.
    """
    if width is None or width < laserfuck_layout.MIN_WIDTH + 2:
        return f"\xff}}}}{run}\n|o^\n _ "

    grid = [[" "] * (width + 1) for _ in range(3)]
    grid[0][0] = "\xff"
    grid[0][1] = "}"
    grid[0][2] = "}"
    grid[1][0] = "|"
    grid[1][1] = "o"
    grid[1][2] = "^"
    grid[2][1] = "_"

    # The funnel occupies rows 1 and 2 at columns 0..2, so the run starts on
    # row 0 and every later segment lands below the funnel, where the margin
    # is free.
    end_row, end_col = laserfuck_layout.fold(grid, run, 0, 3, width)
    grid[end_row][end_col] = "x"
    lines = ["".join(line).rstrip() for line in grid]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _laserfuck_base_groups(values: list[int], count: int) -> list[list[int]]:
    r"""Split the byte values into bands that each get their own base.

    One shared base suits text whose bytes cluster, but most text has two
    clusters and not one -- the letters up near a hundred and the spaces and
    punctuation down in the thirties.  Averaging across both leaves every
    cell a long way from its base, and the residuals are what a base-init
    program spends most of its width on.

    Splitting the *values* (not the tape positions) into bands and giving
    each its own ring cuts that: ``Hello, World!`` falls from 292 units of
    residual to 96.  Each extra ring costs a frame and another walk of the
    tape, so this returns the bands for one split and lets the caller
    measure whether the trade paid.

    Bands are contiguous in value, so a cell belongs to exactly one, and the
    split point is the one minimizing total deviation.
    """
    order = sorted(set(values))
    if len(order) < 2 or count < 2:
        return [values]

    def deviation(band: list[int]) -> int:
        base = min(range(1, 128), key=lambda m: sum(abs(m - v) for v in band))
        return sum(abs(base - v) for v in band)

    best: tuple[int, int] | None = None
    for cut in range(1, len(order)):
        low = set(order[:cut])
        left = [v for v in values if v in low]
        right = [v for v in values if v not in low]
        total = deviation(left) + deviation(right)
        if best is None or total < best[0]:
            best = (total, cut)

    assert best is not None
    low = set(order[: best[1]])
    return [
        [v for v in values if v in low],
        [v for v in values if v not in low],
    ]


def _laserfuck_base_factor(base: int) -> tuple[int, int, int] | None:
    r"""Factor ``base`` into a multiply ring, or decline if literal is shorter.

    Counting a cell up to ``base`` with ``+`` costs ``base`` columns, which
    is most of the width of a base-init program -- 120 of them for a text of
    ``x``.  A ring counts a scratch cell down from ``outer`` and adds
    ``inner`` to the counter each pass, so the cost becomes roughly
    ``outer + inner`` plus a fixed frame, and the shortfall ``rest`` is
    topped up literally.

    That is the same multiply the boolean generator's reader uses.  This
    picks the cheapest split of ``base`` alone; whether the ring is worth
    its frame at all is settled by :func:`laserfuck` building both forms and
    measuring them, because the ring's row competes with the preload's for
    the widest line and no formula here can see that.

    ``None`` means ``base`` is too small to factor at all.
    """
    best: tuple[int, int, int] | None = None
    cost = base
    for outer in range(2, base):
        inner, rest = divmod(base, outer)
        if inner < 1:
            break
        candidate = outer + inner + rest
        if candidate < cost:
            cost, best = candidate, (outer, inner, rest)
    return best


def _laserfuck_base_ring(
    text: str, *, factored: bool = True, grouped: bool = False
) -> str:
    r"""Build the *base-init* LaserFuck program for ``text``.

    Every byte of ``text`` is close to every other -- letters cluster in the
    nineties and hundreds -- so instead of counting each cell up from zero,
    one loop counts *all* of them up together to a shared base, and only the
    differences are written out afterwards.  The base is the value that
    minimizes the total difference, and the residuals are usually a handful
    of ``+``/``-`` each.

    The loop is a ring, laid inline: ``}`` faces the beam along a body that
    walks to cell 0, adds one to every cell on its way back, and decrements
    the counter; ``#`` skips the deflector so ``)`` can test it; and a
    return leg carries the beam back to the ``}``.  That is a different
    shape from the generator's other loop, whose long body is wrapped around
    a serpentine -- this body is deliberately short, which the serpentine
    has nothing to do with.

    The counter ends at zero and *touched*, which byte mode would print as a
    NUL, so a final ``-`` drives it negative where the dump ignores it --
    the same trick the multiplying form uses for its own counter.
    """
    values = [ord(char) for char in text]
    count = len(values)
    bands = _laserfuck_base_groups(values, count) if grouped else [values]

    # Each band gets a base and a ring; a cell reaches its own band's base
    # and is untouched by the others.  ``reached`` tracks what every cell
    # holds once the rings have run, so the tail can write the residuals.
    reached = [0] * count
    stages: list[tuple[int, tuple[int, int, int] | None, list[int]]] = []
    for band in bands:
        if not band:
            continue
        members = set(band)
        base = min(range(1, 128), key=lambda m: sum(abs(m - v) for v in band))
        owned = [i for i, v in enumerate(values) if v in members]
        for index in owned:
            reached[index] = base
        stages.append((base, _laserfuck_base_factor(base) if factored else None, owned))

    scratch = any(factor is not None for _, factor, _ in stages)
    # The counter sits past the text, and a multiply ring's scratch past
    # that.  The first stage's load rides the preload row: the beam descends
    # onto the ring row at a fixed column, so that column has to hold the
    # ring's own '}' and not the tail of a run of ops.
    home = count + 1 if scratch else count
    first_base, first_factor, _ = stages[0]
    preload = ">" * home
    if first_factor is None:
        preload += "<" * (home - count) + "+" * first_base + ">" * (home - count)
    else:
        preload += "+" * first_factor[0]

    tail = "-"
    if scratch:
        # the scratch cell ends at zero and *touched* one cell further on,
        # which byte mode would print as a NUL, so it is cleared too
        tail += ">-<"
    tail += "<" * count
    for index, value in enumerate(values):
        step = value - reached[index]
        tail += ("+" if step > 0 else "-") * abs(step)
        if index < count - 1:
            tail += ">"

    cells: dict[tuple[int, int], str] = {}

    def put(row: int, col: int, char: str) -> None:
        if char != " ":
            cells[(row, col)] = char

    # byte-mode marker, then the funnel that normalizes the start heading
    put(0, 0, "\xff")
    put(0, 1, "}")
    put(0, 2, "}")
    put(1, 0, "|")
    put(1, 1, "o")
    put(1, 2, "^")
    put(2, 1, "_")

    col = 3
    for char in preload:
        put(0, col, char)
        col += 1
    put(0, col, "v")
    put(1, col, "{")
    put(1, 3, "v")

    # Rings run left to right along row 2, each with its return leg on row
    # 3: '^' under the ring's own '}' and '{' under its '/'.  A multiply
    # ring, when there is one, goes first and hands the counter to the
    # spread ring already loaded.
    col = 3

    def put_ring(ops: str) -> None:
        nonlocal col
        start = col
        put(2, col, "}")
        col += 1
        for char in ops + "#/)":
            put(2, col, char)
            col += 1
        put(3, start, "^")
        put(3, col - 2, "{")

    def put_ops(ops: str) -> None:
        nonlocal col
        for char in ops:
            put(2, col, char)
            col += 1

    for position, (base, factor, owned) in enumerate(stages):
        if factor is None:
            # count the counter up to the base one unit at a time; the
            # first stage's run is already on the preload row
            if position:
                put_ops("+" * base)
        else:
            # a scratch cell one past the counter drives the multiply: it
            # counts down from 'outer', adding 'inner' each pass, and the
            # shortfall is topped up on the way back
            outer, inner, residual = factor
            if position:
                # a later stage starts on the counter, so it has to step out
                # to the scratch cell before loading the multiply
                put_ops(">" + "+" * outer)
            put_ring("<" + "+" * inner + ">" + "-")
            put_ops("<" + "+" * residual)
        # the spread ring: walk to cell 0, add one to this band's cells
        # only, walk back to the counter and spend a pass
        # The ring tests the cell it starts on, so the body has to come
        # back to exactly that cell -- the counter -- before it decrements.
        members = set(owned)
        spread = "<" * count
        for index in range(count):
            if index in members:
                spread += "+"
            if index < count - 1:
                spread += ">"
        spread += ">" + "-"
        put_ring(spread)

    for index, char in enumerate(tail):
        put(2, col + index, char)
    put(2, col + len(tail), "x")

    height = max(row for row, _ in cells) + 1
    span = max(c for _, c in cells) + 1
    lines = [
        "".join(cells.get((row, c), " ") for c in range(span)).rstrip()
        for row in range(height)
    ]
    return "\n".join(lines)


def laserfuck(text: str, width: int | None = None) -> str:
    """Build a LaserFuck program that outputs ``text``, the smaller of two.

    Two constructions are available and which wins depends entirely on the
    text.  :func:`_laserfuck_multiply` factors the byte values and adds them
    in base-sized chunks, which is best when they are spread out.
    :func:`_laserfuck_base_ring` counts every cell up to a shared base in one
    loop and then writes only the differences, which is best when they
    cluster -- exactly when the multiply passes stop paying and the other
    form falls back to writing one ``+`` per unit.

    Rather than predict, both are built and the smaller grid is returned.  A
    ``width`` disqualifies a form that cannot meet it; if neither can, the
    multiplying form's own fallback still applies.
    """
    forms = [_laserfuck_multiply(text, width)]
    for factored in (False, True):
        for grouped in (False, True):
            ring = _laserfuck_base_ring(text, factored=factored, grouped=grouped)
            if width is None or max(map(len, ring.split("\n"))) <= width:
                forms.append(ring)
    return min(
        forms, key=lambda form: (form.count("\n") + 1) * max(map(len, form.split("\n")))
    )


def _laserfuck_multiply(text: str, width: int | None = None) -> str:
    """Build a LaserFuck program that outputs ``text``.

    Phase 1 generates a brainfuck-style program: each pass picks a base about
    the square root of the largest remaining value, emits a ``+[>+...+<-]``
    loop that adds each value's base-aligned chunk, then reduces the values by
    that base.  Phase 2 lays the program onto the grid, with the first loop's
    body wrapped around a serpentine track on the edges so the laser travels
    around it.

    ``width``, when given, is a hard bound on the columns of whatever this
    returns, and both forms fold to honour it.  The *linear* form is a
    straight run of tape code, so it zigzags into rows the way any run does
    (:func:`~esolangs.tools.laserfuck_layout.fold`).

    The looping form cannot break between any two cells: a ``]``'s mirror
    bounces the beam back to cells placed relative to its matching ``[``,
    so a bracket pair split across two folded segments has no return path.
    It folds between whole *bracket spans* instead -- a depth-0 ``[`` to
    the ``]`` that closes it, mirrors and all, is one unbreakable token --
    which is the same token-aware rule the line-oriented wrappers in
    :mod:`esolangs.tools.wrap` follow, applied to a grid
    (:func:`~esolangs.tools.laserfuck_layout.fold_groups`).

    A span is indivisible, so a width too narrow for the widest one is the
    floor: there the linear form is emitted instead, which fits by being
    several times larger (measured over 200 random strings, a median 4.3x).
    Hello-World folds into 80 columns as a loop and stays the smaller
    program.  ``width=None`` (the default everywhere but the example
    writers) returns the unfolded loop form untouched.
    """
    _require_bytes(text, "LaserFuck")
    values = [ord(c) for c in text]
    code = ""
    linear = "".join(">" + "+" * ord(c) for c in text).rstrip(">")

    def chunks(base: int) -> str:
        # one '>' then '+' per value's base-chunk, ending back at the left
        return "".join(">" + "+" * (n // base) for n in values).rstrip(">")

    while True:
        top = max(values)
        base = math.isqrt(top)
        fallback = chunks(1)  # the linear program: add each value directly

        if not top:
            break

        if all(values):
            base = min(base, *values)

        ops = chunks(base)
        cells = ops.count(">")  # how many cells the loop body crosses

        if cells < 11:
            ops += cells * "<"  # move back to the counter cell
        else:
            ops += "[<]>"  # a wide loop re-enters from the left instead

        ops = "+" * base + f"[{ops}-]"

        # keep this pass only if it beats the linear fallback in size
        if len(fallback) - len(ops) - ops.count("[") * 7 < 0:
            break

        code += ops
        values = [k % base for k in values]

    if code:
        # the counter cell would end at 0 and be dumped as a NUL; a final "-"
        # makes it negative, which the interpreter's output excludes
        code += "-"

    if "[" not in code:
        return _laserfuck_linear(fallback, width)

    # -- lay the program out onto the grid --
    match = re.search(r"\[([^[\]]*)", code)
    loop = match[1] if match else ""
    frame = code.replace(loop, "", 1).replace("[]", "[}]")
    loop_col = frame.find("[") + 8  # grid column of the loop's opening bracket

    # Build the frame as a list of (top, middle, bottom) groups: what the
    # frame writes on its own row, and the mirror cells that must stay
    # directly beneath it.  A bracket marker and its mirrors are one group,
    # which is what lets a width fold the frame between two of them without
    # separating a marker from the cells that serve it.
    # A group is one *top-level* token: a single tape op, or a whole
    # balanced bracket span from a depth-0 "[" to the "]" that closes it.
    # The span is the unbreakable unit, not the marker: a "]"'s "/" bounces
    # the beam back to cells placed relative to its matching "[", so a pair
    # split across two folded segments has no return path.
    groups: list[tuple[str, str, str]] = []
    depth = 0
    entry_index = None  # the group holding the first "[" marker
    parts: list[tuple[str, str, str]] = []

    for c in frame:
        if c == "[":
            top_cell, bottom_cell, depth = "v }  }", "}#^)#^", depth + 1
            if entry_index is None:
                entry_index = len(groups)  # the group this "[" ends up in
        elif c == "]":
            top_cell, bottom_cell = "#/)", " / "
        else:
            top_cell, bottom_cell = c, " "

        pad_row = 2 - (depth == 2)  # a nested loop also uses the middle row
        pad = " " * len(top_cell)
        middle, bottom = (bottom_cell, pad) if pad_row == 1 else (pad, bottom_cell)
        parts.append(
            (top_cell, middle.ljust(len(top_cell)), bottom.ljust(len(top_cell)))
        )

        if c == "]":
            depth -= 1

        if depth == 0:
            # back at the top level: everything buffered is one group
            tops, mids, bots = zip(*parts, strict=True)
            groups.append(("".join(tops), "".join(mids), "".join(bots)))
            parts = []

    if parts:  # an unbalanced frame: keep it whole rather than dropping it
        tops, mids, bots = zip(*parts, strict=True)
        groups.append(("".join(tops), "".join(mids), "".join(bots)))

    # The first "[" marker's stub is a placeholder: the loop track connects
    # back into the frame at ``loop_col`` instead, so blank it out.  Doing
    # it inside the group -- before the frame is laid out -- keeps it
    # correct whether or not the frame is folded.  A second "[" immediately
    # after has its leading "v" swallowed too, matching a bracket that
    # directly follows another one.
    if entry_index is not None:
        entry_top, entry_middle, entry_bottom = groups[entry_index]
        start = entry_top.index("}")
        end = start + len("}  }")
        if entry_top[end : end + 1] == "v":
            end += 1
        entry_top = entry_top[:start] + " " * (end - start) + entry_top[end:]
        groups[entry_index] = (entry_top, entry_middle, entry_bottom)

    frame_width = 3 + sum(len(g[0]) for g in groups)
    # Bind the width the fold runs at, so it stays a plain int throughout the
    # folded path; ``None`` means the frame fits and is laid out unfolded.
    fold_width = width if width is not None and frame_width > width else None
    fold_frame = fold_width is not None

    if fold_width is not None:
        # A single group is indivisible, so one wider than a folded segment
        # cannot be laid at this width however many rows it is given.  The
        # linear form is the floor for those: bigger, but it folds.
        room = laserfuck_layout.segment_width(fold_width)
        if max(len(g[0]) for g in groups) > room:
            return _laserfuck_linear(linear, width)

    if fold_width is not None:
        # The frame overruns the width, so fold it between groups.  This
        # keeps the compact loop program rather than falling back to the
        # linear form, which fits by being several times larger.
        frame_cells = [[" "] * (fold_width + 1) for _ in range(3)]
        frame_cells[0][1] = "}"
        frame_cells[0][2] = "}"
        frame_cells[1][0] = "|"
        frame_cells[1][1] = "o"
        frame_cells[1][2] = "^"
        frame_cells[2][1] = "_"
        end_row, end_col = laserfuck_layout.fold_groups(
            frame_cells, groups, 0, 3, fold_width
        )
        # The frame no longer ends at the top right, so the reversed-tail
        # trick the unfolded path uses does not apply: the fallback run
        # carries straight on from wherever the fold left the beam, folding
        # again if it has to, and the "x" goes where that ends.
        if fallback:
            # Carry on across the frame's own row until the turn, then drop
            # past its two mirror rows before folding further -- those rows
            # belong to the last segment's markers, and writing the run
            # into them would land tape code under a mirror.
            room = laserfuck_layout.segment_width(fold_width) + laserfuck_layout.MARGIN
            head = fallback[: max(room - end_col, 0)]
            for char in head:
                frame_cells[end_row][end_col] = char
                end_col += 1
            rest = fallback[len(head) :]
            if rest:
                laserfuck_layout.reserve(frame_cells, end_row + 3)
                frame_cells[end_row][end_col] = "v"
                frame_cells[end_row + 3][end_col] = "{"
                frame_cells[end_row + 3][laserfuck_layout.MARGIN] = "v"
                end_row += 4
                laserfuck_layout.reserve(frame_cells, end_row)
                frame_cells[end_row][laserfuck_layout.MARGIN] = "}"
                end_row, end_col = laserfuck_layout.fold(
                    frame_cells, rest, end_row, laserfuck_layout.MARGIN + 1, fold_width
                )
        frame_cells[end_row][end_col] = "x"
        grid = ["".join(line).rstrip() for line in frame_cells]
        while grid and not grid[-1]:
            grid.pop()
    else:
        grid = [" }}", "|o^", " _ "]
        for group_top, group_middle, group_bottom in groups:
            grid[0] += group_top
            grid[1] += group_middle
            grid[2] += group_bottom

    track_len = len(loop) + loop_col
    overhang = len(fallback) + loop_col - (len(grid[0]) - 2)
    prefix = (max(overhang, 0) // 2) + 1  # fallback chars that fit on the top row

    if not fold_frame:
        if fallback:
            grid[0] += fallback[:prefix] + "^"
            remainder = fallback[prefix:]
            exit_row = f"x{remainder[::-1]}{{"
            grid.insert(0, exit_row.rjust(len(grid[0])))
        else:
            grid[0] += "x"  # no fallback: the frame ends by killing the laser

    # A folded frame is bounded by the width rather than by its longest
    # row, so the serpentine has the whole width to lay its track in.
    row_width = fold_width if fold_width is not None else len(grid[0])
    tracks = 2

    # enough serpentine rows to hold the loop body around the frame
    while (track_len // tracks) > row_width:
        tracks += 1

    tracks += tracks % 2  # even, so the serpentine joins back on the left
    per_row = (track_len // tracks) + 1
    offset = per_row + 1

    if len(loop) <= offset or tracks > 2:
        # a loop body that fits on the top row, or a grid too narrow for the
        # serpentine's return path to connect, cannot route the laser back
        # through the body; emit the linear program instead
        return _laserfuck_linear(linear, width)

    # top row: output-mode byte, the loop start, then a turn down
    grid.insert(0, f"\xff}}{loop[:offset]}v")

    # the single serpentine row carries the rest of the loop body around the
    # frame (the guard above rejects every input needing more than one, so
    # ``tracks`` is always 2 here).  Its content right-justifies into
    # ``per_row`` columns after a "  v" lead-in, but the first ``loop_col``
    # columns of that padding are blank -- overwrite exactly those with the
    # connector that ties the row's left end back into the frame at the
    # loop entry, instead of leaving it as a fresh (unused) turn down.
    part = loop[offset : offset + per_row]
    row = "  v" + part[::-1].rjust(per_row) + "{"
    connector = f" ^{' ' * (loop_col - 5)}{{  {{v "
    grid.insert(1, connector + row[len(connector) :])

    # The frame is as narrow as this geometry gets, so if it still overruns
    # the width, no fold of it will help -- fall back to the linear form,
    # which is bigger but foldable.  This is the same escape the two guards
    # above take, for the same reason: the loop layout cannot be had at
    # this width.
    if width is not None and max(map(len, grid)) > width:
        return _laserfuck_linear(linear, width)

    return "\n".join(grid)


def magnitude(text: str) -> str:
    """Build a %^2^-1 program that outputs ``text`` (delta encoding).

    Each character is produced as a delta from the previous one.  ``s`` and
    ``i`` scale toward powers of 2 and 3, ``p`` flips the sign, ``e`` prints
    the accumulated magnitude as a byte, and a leading ``'`` resets to an
    absolute (non-delta) encoding when the delta would overshoot the target.
    """
    _require_bytes(text, "%^2^-1")

    def close(val: int, start: int) -> int:
        if start > val:
            return 0

        while start <= val:
            start *= 2

        return start // 2

    mode = True
    prog = ""
    last = 0

    for c in text:
        n = ord(c) - last

        if abs(n) > ord(c):
            prog += "'"
            mode = True
            last = 0
            n = ord(c)

        if n and mode == (n < 0) and last:
            prog += "p"
            mode = not mode

        n = abs(n)

        if not last:
            x = close(n, 2)
            y = close(n, 3)

            if n - x < n - y:
                num = _ilog(2, x // 2)
                prog += "s" + num * "m"
                n -= x
            elif y:
                num = _ilog(2, y // 3)
                prog += "i" + num * "m"
                n -= y

        if n == 1:
            prog += "ips"
            mode = not mode
        elif n > 2:
            q, r = divmod(n, 3)
            if r == 1:
                q, r = q - 1, r + 3
            prog += q * "i"
            n = r

        prog += (n // 2) * "s" + ("p" if mode else "") + "e"
        last = ord(c)
        mode = False

    return prog


def painfuck(text: str) -> str:
    """Build a Painfuck program that outputs ``text``.

    Each character is built as a signed delta from the previous one.  ``p``
    and ``s`` push and scale toward the target value on a wrapping tape,
    ``c``/``t``/``rl`` handle the arithmetic in bases 7 and 3 with a pointer
    loop, and ``u`` prints the current cell as a byte.
    """
    _require_bytes(text, "Painfuck")

    def add(val: int) -> str:
        return (val // 2) * "p" + (val % 2) * "ps"

    def close(val: int, s: str, op: str) -> tuple[int, str]:
        if val > 7:
            pwr = _ilog(7, val)
            s += pwr * "c" + op
            val -= 7**pwr
        if val:
            pwr = 1
            while 2 * val >= (3**pwr - 1):
                pwr += 1

            s += op + (pwr - 2) * "t"
            val -= (3 ** (pwr - 1) - 1) // 2

        return val, s

    def loop(val: int, s: str, op: str) -> tuple[int, str]:
        sqr = math.isqrt(val)

        if sqr > 3:
            # "rl" advances the pointer by one from any cell; "lr" would
            # stall when the pointer is at cell 0
            s += "rl" + add(sqr) + "al"

            if op == "p":
                s += add(sqr)
            else:
                s += sqr * "s"

            s += "rl" + "sbl"
            val -= sqr**2

        return val, s

    res = ""
    last = 0

    for c in text:
        n = ord(c) - last

        if abs(n) > ord(c):
            res += "rl"
            n = ord(c)

        if n > 0:
            if n % 2:
                res += "ps"

            n, res = close(n // 2, res, "p")
            n, res = loop(n * 2, res, "p")
            res += add(n)
        elif n < 0:
            n = abs(n)
            n, res = close(n, res, "s")
            n, res = loop(n, res, "s")
            res += n * "s"

        last = ord(c)
        res += "u"

    # The two output cycles substitute each emitted character by the one
    # ``k`` steps further along its cycle, keeping the tape uncluttered.
    cycles = ["rwzjkvep", "dlahiqbostcuy"]
    shifted = ""
    for k, ch in enumerate(res):
        for cycle in cycles:
            if ch in cycle:
                n = cycle.find(ch)
                shifted += cycle[(n + k) % len(cycle)]

    return shifted


def one_two_three(text: str) -> str:
    """Build a 1/2 program per character, terminated by a trailing 1.

    ``edi`` carries the running XOR of the characters, so each segment only
    emits the difference from the previous character.  ``esi`` walks down the
    bits of that difference: ``2`` clears a bit position and ``122`` sets it
    (an XOR) before continuing.  Then a ``121`` march doubles ``esi`` up to
    512, where ``2`` outputs ``edi`` as a character and resets ``esi``.  The
    final ``1`` leaves ``esi`` above 128 so the program halts at the
    terminator.

    Input to a 123 program is appended at the end of the program, separated
    from it by a single ``|``.
    """
    _require_bytes(text, "123")
    res = ""
    last = 0

    for c in text:
        bits = bin(ord(c) ^ last)[2:].zfill(8).rstrip("0")
        n = len(bits)

        if n:
            # walk down the bits; the last is always 1, so dropping the final
            # "22" leaves esi at 2 instead of 0
            walk = bits.replace("0", "2").replace("1", "122")
            # a "121" toggles a bit twice (a no-op on edi) while doubling esi;
            # n doublings carry esi from 2 to 512, where the final "2" outputs
            march = "121" * n
            res += walk[:-2] + march[:-1]
        else:
            res += "12112"  # no difference: just march esi up and output
        last = ord(c)

    return res + "1"


def myscript(text: str, width: int | None = None) -> str:
    r"""Generate a MyScript program that outputs ``text``.

    MyScript's string literals support the escapes ``\\0 \\n \\\\ \\t \\f
    \\"`` and literal printable ASCII, so ``text`` is emitted as one ``say``
    of the escaped string; any other byte (unrepresentable in the language)
    is rejected.

    A ``width`` splits the text across several ``say`` lines.  The escaped
    pieces are what get packed, never the characters inside one: breaking
    ``\\n`` in half would leave a stray backslash and change what the
    program prints, which is the same reason the literal cannot simply be
    reflowed by :mod:`~esolangs.tools.wrap`.
    """
    res: list[str] = []
    for c in text:
        if c == "\\":
            res.append("\\\\")
        elif c == '"':
            res.append('\\"')
        elif c == "\0":
            res.append("\\0")
        elif c == "\n":
            res.append("\\n")
        elif c == "\t":
            res.append("\\t")
        elif c == "\f":
            res.append("\\f")
        elif 32 <= ord(c) < 127:
            res.append(c)
        else:
            raise ValueError("MyScript can only output its representable bytes")
    if width is None or width <= 0:
        return 'say "' + "".join(res) + '"'
    # ``say ""`` is six characters around the escaped text.
    budget = max(1, width - len('say ""'))
    lines: list[str] = []
    current = ""
    for piece in res:
        if current and len(current) + len(piece) > budget:
            lines.append(current)
            current = ""
        current += piece
    if current or not lines:
        lines.append(current)
    return "\n".join(f'say "{line}"' for line in lines)


def nocomment(text: str) -> str:
    """Generate a NoComment program that outputs ``text``.

    The current cell is driven in place from one character's value to the
    next with ``i``/``d`` runs (increment/decrement wrap the 8-bit cell),
    and ``o`` prints it as a byte, so each character costs only its delta
    from the previous one rather than its full code.
    """
    _require_bytes(text, "NoComment")
    res: list[str] = []
    prev = 0
    for c in text:
        n = ord(c)
        delta = n - prev
        if delta >= 0:
            res.append("i" * delta)
        else:
            res.append("d" * -delta)
        res.append("o")
        prev = n
    return "".join(res)


def unsquare(text: str) -> str:
    """Generate an Unsquare program that outputs ``text``.

    ``OA``/``IA`` push 0/1 and ``A`` loads it into the accumulator, ``+``
    adds 2, ``-`` subtracts 2, and ``x`` doubles, so a character is built
    from a parity seed (``O`` for even, ``I`` for odd) followed by the
    shortest program to the code: doubling makes even values O(log n), with
    ``+`` runs covering the rest.  ``P`` pushes the accumulator and ``o``
    prints it.

    ``o`` prints without popping and neither ``P`` nor ``o`` touches the
    accumulator, so it still holds the previous character when the next one
    starts.  Each character is therefore reached from *that* value when a
    ``+``/``-``/``x`` chain off it is shorter than reseeding -- which it
    usually is, since adjacent code points are close: ``"Hello, World!"``
    drops 21% and a repeated letter costs two characters instead of ``2 +
    O(log n)``.

    Parity is what bounds the reuse: ``x`` sends an odd value to an even one
    and nothing restores oddness, so an odd target is reachable only by a
    ``+``/``-`` run from an odd value.  When the accumulator is even and the
    target odd there is no chain at all and the seed is reloaded, which is
    why alternating-parity text (``"abcdefgh"``) is unchanged.
    """
    _require_bytes(text, "Unsquare")

    @cache
    def build(start: int, v: int) -> str | None:
        """Shortest ``+``/``-``/``x`` run from ``start`` to ``v``, if any.

        Breadth-first, so the first arrival at a value is its cheapest.  The
        band is bounded below by ``-2`` and above by twice the largest byte:
        a chain that leaves it can only come back by retracing, so nothing
        outside can be on a shortest path.
        """
        if v == start:
            return ""
        if start % 2 == 0 and v % 2:
            return None
        queue = deque([(start, "")])
        seen = {start}
        while queue:
            value, run = queue.popleft()
            for op, moved in (("+", value + 2), ("-", value - 2), ("x", value * 2)):
                if moved == v:
                    return run + op
                if -2 <= moved <= 2 * 0xFF and moved not in seen:
                    seen.add(moved)
                    queue.append((moved, run + op))
        return None

    def seed(v: int) -> str:
        """Reload the parity constant and climb to ``v`` from there."""
        run = build(v % 2, v)
        if run is None:  # pragma: no cover - a seed shares the target's parity
            raise AssertionError(f"no run to {v} from its own parity")
        return ("I" if v % 2 else "O") + "A" + run

    res: list[str] = []
    acc: int | None = None
    for char in text:
        value = ord(char)
        best = seed(value)
        if acc is not None:
            chain = build(acc, value)
            if chain is not None and len(chain) < len(best):
                best = chain
        res.append(best + "Po")
        acc = value
    return "".join(res)


def home_row(text: str) -> str:
    """Generate a Home Row program that outputs ``text``.

    Each character is built as ``a * b + r`` on a target cell by a counter
    loop: ``a``-run sets the counter, an ``l`` loop adds ``b`` to the target
    and decrements the counter each pass, and an ``a``-run tops the product
    up before ``k`` prints the target and resets it (the spec's 5x5 grid
    initializes at zero).  ``a`` is searched near ``sqrt(ord)`` so the
    program is O(sqrt) rather than O(ord).  A NUL uses a net-zero ``ask`` so
    it cannot collapse into the adjacent ``k``s.
    """
    _require_bytes(text, "Home Row")

    def segment(value: int) -> str:
        a, b, r = _factor_triple(value)
        # counter cell 0, target cell 1: "f" moves 0 -> 1 and four "f"s wrap
        # 1 -> 0 back.  The loop body adds b to the target and decrements
        # the counter.
        return (
            "a" * a
            + "l"
            + "f"
            + "a" * b
            + "f" * 4
            + "s"
            + "l"
            + "f"
            + "a" * r
            + "k"
            + "f" * 4
        )

    res = ["ask" if ord(c) == 0 else segment(ord(c)) for c in text]
    return "".join(res) + ";"


def taglate(text: str) -> str:
    """Generate a Taglate program that outputs ``text``.

    The first line seeds the queue with the text itself, and one ``i`` per
    character pops and prints it.  A newline cannot appear in the text
    because it would split the queue line.
    """
    if any(c in _SPLITLINES for c in text):
        raise ValueError(
            "Taglate cannot output a newline or other line break "
            "(the queue is one line)"
        )
    return text + "\n" + "i" * len(text)


def dimensional(text: str) -> str:
    """Build a Dimensional program that outputs ``text``.

    ``=`` sets the current cell to a two-digit hexadecimal literal and ``.``
    prints it as a byte, so each character is a two-part run.  The pointer
    stays at the first cell throughout.
    """
    _require_bytes(text, "Dimensional")
    return "".join(f"={ord(c):02x}." for c in text)


def _pct_path(byte: int) -> str:
    """%^2^-1 program from ``'`` (acc = 0) to ``byte``.

    Reverse ``s`` (acc -= 2), ``i`` (acc -= 3), ``m`` (acc *= 2) to reduce the
    byte to 0: halve when even (biggest reduction), otherwise subtract 2 or 3,
    then a final ``p`` flips the accumulated negative to the byte.  Byte 1 is
    the one value the +2/+3/*2 ops cannot build (it needs the ``p`` negate
    mid-way) and is a fixed 3-op constant.  The greedy is within 3 ops of the
    shortest program for every byte and keeps the accumulator bounded well
    under the interpreter's ``acc > 3003`` reset.
    """
    if byte == 0:
        return ""
    if byte == 1:
        return "ips"
    build = []
    while byte > 0:
        if byte % 2 == 0 and byte > 4:
            build.append("m")
            byte //= 2
        elif byte % 2 == 0:
            build.append("s")
            byte -= 2
        else:
            build.append("i")
            byte -= 3
    return "".join(reversed(build)) + "p"


def pct_squared_minus_one(text: str) -> str:
    """Build a %^2^-1 program that outputs ``text``.

    Two generators exist with complementary strengths, and the function
    returns the shorter of the two for the given text:

    - ``_pct_path``: each byte is built from ``'`` (reset) via a path that
      scales and negates the accumulator to the byte value, then ``e`` prints
      it.  Best for high-delta text (each byte is encoded independently).
    - :func:`magnitude`: each character is a delta from the previous one, so
      ``s``/``i`` scale toward powers of 2 and 3 and ``p`` flips the sign.
      Best for low-delta, repetitive text.
    """
    _require_bytes(text, "%^2^-1")
    absolute = "".join("'" + _pct_path(ord(c)) + "e" for c in text)
    return min((absolute, magnitude(text)), key=len)


def basicfuck(text: str) -> str:
    """Build a Basicfuck program that outputs ``text``.

    One variable ``a`` tracks the current byte: ``+=``/``-=`` walk it to each
    character (within the declared ``0..255`` range) and ``write <- a ;``
    prints it.  ``o=nearest`` pins any accidental overshoot back to the range.
    """
    _require_bytes(text, "Basicfuck")
    res = ["#basicfuck t=1 r=0~255 o=nearest", "#allocate a"]
    cur = 0
    for c in text:
        t = ord(c)
        delta = t - cur
        res.append(f"a += {delta};" if delta >= 0 else f"a -= {-delta};")
        res.append("write <- a ;")
        cur = t
    return "\n".join(res) + "\n"


def bit_tilde(text: str) -> str:
    """Build a bit~ program that outputs ``text``.

    The tape holds bits: ``~`` flips the current bit, ``>`` moves right, and
    ``(`` prints the 8-bit window as a byte.  The generator tracks the tape so
    it only toggles bits that must change, and walks back to cell 0 to print.
    """
    _require_bytes(text, "bit~")
    res = []
    tape = [0] * 8
    for c in text:
        bits = [int(b) for b in format(ord(c), "08b")]
        for i in range(8):
            if tape[i] != bits[i]:
                res.append("~")
                tape[i] = bits[i]
            if i < 7:
                res.append(">")
        res.append("<" * 7 + "(")
    return "".join(res)


def forbin(text: str) -> str:
    """Build a Forbin program that outputs ``text``.

    Forbin's ``out`` writes one byte as eight bit arguments (most significant
    first), so each character becomes one ``out`` line inside ``main``.
    """
    _require_bytes(text, "Forbin")
    lines = ["main {"]
    for char in text:
        bits = ",".join(str((ord(char) >> k) & 1) for k in range(7, -1, -1))
        lines.append(f"  out {bits};")
    lines.append("}")
    return "\n".join(lines)


def three_x(text: str, width: int | None = None) -> str:
    """Build a 3x program that outputs ``text``.

    ``[`` prints the literal up to the next ``]`` and skips past it, so the
    program is ``[text]``; a ``]`` in the text would end the literal early.

    A ``width`` splits the text across several ``[...]`` literals, one per
    line.  The literal cannot be broken by :mod:`~esolangs.tools.wrap` -- a
    newline between the brackets is a character the program would print --
    so honouring a width means emitting a different program rather than
    reflowing this one.
    """
    if "]" in text:
        raise ValueError("3x cannot output ']' (it would end the literal)")
    chunks = _literal_chunks(text, width, len("[]"))
    return "\n".join("[" + chunk + "]" for chunk in chunks)


def sbleq(text: str) -> str:
    """Build an S*bleq program that outputs ``text``.

    Each character becomes an output instruction ``-3 <data> 0`` that prints
    the value stored at ``<data>``; the character values are embedded as data
    at the end of the program, and a final ``0 0 <sentinel>`` halts by
    jumping to a past-the-end address.  This mirrors the Subleq wiki's own
    Hello World, which stores the output characters as literal data.
    """
    _require_bytes(text, "S*bleq")
    n = len(text)
    cells: list[int] = []
    for i in range(n):
        cells += [-3, 3 * n + 3 + i, 0]
    sentinel_addr = 3 * n + 3 + n
    cells += [0, 0, sentinel_addr]
    cells += [ord(c) for c in text]
    cells += [len(cells) + 1]
    return " ".join(map(str, cells))


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
        return min((ringed, folded), key=len)
    # Both shapes are built and the shorter one wins, rather than predicting
    # the winner from the code point: the two layouts are what they cost.
    straight = _streetcode_straight(instructions)
    ring = _streetcode_ring(text) if text else None
    if ring is None:
        return straight
    return min((ring, straight), key=len)


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


def suptiftam(text: str) -> str:
    """Build a Suptiftam program that outputs ``text``.

    Each character is written to the ``term`` tape's current cell as a byte
    literal and the head moves right, one statement pair per character.
    A byte literal is a single printable non-whitespace ASCII character, so
    the alphabet is printable ASCII plus space; the single quote (the
    literal's delimiter) and tab (a comment marker) cannot be emitted.
    """
    for c in text:
        if not 32 <= ord(c) <= 126 or c == "'":
            raise ValueError(
                "Suptiftam can only output printable non-quote ASCII (32-126 except ')"
            )
    return "\n".join(f"term='{c}'\nright(:term:)" for c in text)
