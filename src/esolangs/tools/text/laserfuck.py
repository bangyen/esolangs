"""The LaserFuck text generator.

One language, one file -- the pattern the boolean package already follows
for its larger generators (``wii2d.py``, ``streetcode.py``,
``circuit_diagram.py``).  LaserFuck earns it: at ~730 lines it was a third
of ``other.py``, and it is the only text generator that lays out a grid,
folds two competing constructions, and rotates a block to meet a width.

Two constructions are built and the smaller grid wins; see
:func:`laserfuck`.
"""

import math
import re

from esolangs.tools import laserfuck_layout
from esolangs.tools.text.helpers import _require_bytes

__all__ = ["laserfuck"]


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
    if width is None or width < laserfuck_layout.MIN_WIDTH + 1:
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

    def total(cut: int) -> int:
        low = set(order[:cut])
        return deviation([v for v in values if v in low]) + deviation(
            [v for v in values if v not in low]
        )

    # ``order`` has at least two distinct values, so there is always at
    # least one cut to choose from
    low = set(order[: min(range(1, len(order)), key=total)])
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
            break  # pragma: no cover - outer < base keeps inner at least 1
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
            continue  # pragma: no cover - the grouper emits no empty band
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


def _laserfuck_snake(body: str, spine: int, right: int) -> list[str] | None:
    """Lay a ring body across rows between fixed margins.

    Row 0 carries the entry ``}`` at ``spine`` and runs rightward; every
    later row starts at ``spine + 1``.  Rightward rows drop at ``right``,
    leftward rows drop at ``spine + 1``, and the row below always catches
    in the same column.  A leftward row is written right-to-left, which is
    the order its beam reads -- no reversal is needed on top of that.

    The last body row has to be a leftward one, because the test ``-#/)``
    is read rightward and a leftward beam would meet its ``)`` first; an
    empty turn row is added when the body would otherwise end going right.

    ``body`` must *not* carry the counter's ``-``: the test row supplies it,
    and a body that decrements too would spend the counter twice a pass.
    """
    body = body[:-1] if body.endswith("-") else body
    left = spine + 1
    first = right - spine - 1
    rest_width = right - left - 1
    if first < 1 or rest_width < 1:
        return None

    chunks = [body[:first]]
    remaining = body[first:]
    while remaining:
        chunks.append(remaining[:rest_width])
        remaining = remaining[rest_width:]
    if len(chunks) % 2 == 1:
        chunks.append("")

    grid = [[" "] * (right + 6) for _ in range(len(chunks) + 2)]
    for index, chunk in enumerate(chunks):
        row = grid[index]
        if index % 2 == 0:
            start = spine if index == 0 else left
            row[start] = "}"
            for offset, char in enumerate(chunk):
                row[start + 1 + offset] = char
            row[right] = "v"
        else:
            row[right] = "{"
            for offset, char in enumerate(chunk):
                row[right - 1 - offset] = char
            row[left] = "v"

    test = len(chunks)
    grid[test][left] = "}"
    for offset, char in enumerate("-#/)"):
        grid[test][left + 1 + offset] = char
    grid[test + 1][left + 3] = "{"
    grid[test + 1][spine] = "^"
    return ["".join(row).rstrip() for row in grid]


def _laserfuck_snake_ring(text: str, width: int) -> str | None:
    r"""Build a base-init program whose rings are snaked across rows.

    A ring body cannot be folded the way a straight run of ops can -- the
    return leg re-enters at the ``}`` and re-runs the whole body, so a body
    split by :func:`~esolangs.tools.laserfuck_layout.fold` would re-execute
    only its tail.  It can be *snaked*, though, and that is what lets a
    base-init program meet a width instead of falling back to the linear
    form: :func:`_laserfuck_snake` walks the body across as many rows as it
    needs and only then reaches the test.

    Rings stack as self-contained blocks, each with its own spine and
    return leg.  Nothing is shared between them: the beam leaves a block
    through the ``)`` on its test row, a ``v`` drops it clear of the return
    leg, and a ``}`` on a fresh row faces it right again for whatever comes
    next.  The residual tail is caught the same way and folded, since it is
    direction-agnostic ops.

    Returns ``None`` when ``width`` cannot hold the frame.
    """
    values = [ord(char) for char in text]
    count = len(values)
    base = min(range(1, 128), key=lambda m: sum(abs(m - v) for v in values))

    # Writing the base out one '+' at a time would push the first spine
    # past the width before the body even starts, so it is factored into a
    # multiply block whenever that is shorter.
    factor = _laserfuck_base_factor(base)
    scratch = factor is not None
    home = count + 1 if scratch else count

    # the spread ring starts and ends on the counter, which is the cell its
    # own test looks at -- a body that came back anywhere else would spend
    # the wrong cell and never terminate
    spread = "<" * count + "+" + ">+" * (count - 1) + ">"
    tail = "-"
    if scratch:
        tail += ">-<"
    tail += "<" * count
    for index, value in enumerate(values):
        step = value - base
        tail += ("+" if step > 0 else "-") * abs(step)
        if index < count - 1:
            tail += ">"

    if factor is not None:
        outer, inner, residual = factor
        stages = [
            (">" * home + "+" * outer, "<" + "+" * inner + ">"),
            ("<" + "+" * residual, spread),
        ]
    else:
        stages = [(">" * home + "+" * base, spread)]

    right = width - 2
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

    row, entry = 0, 3
    for preload, body in stages:
        col = entry
        for char in preload:
            put(row, col, char)
            col += 1
        spine = col
        if spine >= right - 2:
            return None
        # drop the beam into this block's entry '}', directly below
        put(row, spine, "v")
        block = _laserfuck_snake(body, spine, right)
        if block is None:
            return None  # pragma: no cover - the spine guard above covers it
        for offset, line in enumerate(block):
            for index, char in enumerate(line):
                put(row + 1 + offset, index, char)
        # the test row is the second from the end of the block
        test_row = row + 1 + len(block) - 2
        exit_col = spine + 6
        put(test_row, exit_col, "v")
        row = test_row + 2
        put(row, exit_col, "}")
        entry = exit_col + 1

    height = max(index for index, _ in cells) + 1
    span = max(index for _, index in cells) + 1
    depth = laserfuck_layout.rows_needed(len(tail) + 1, width)
    grid = [[" "] * (max(width, span) + 2) for _ in range(height + depth + 3)]
    for (index, col), char in cells.items():
        grid[index][col] = char

    end_row, end_col = laserfuck_layout.fold(grid, tail, row, entry, width)
    grid[end_row][end_col] = "x"
    lines = ["".join(line).rstrip() for line in grid]
    while lines and not lines[-1]:
        lines.pop()
    if max(map(len, lines)) > width:
        return None
    return "\n".join(lines)


def _laserfuck_columns(program: str) -> int:
    """Return the widest row of ``program``, which is what a width bounds."""
    return max(map(len, program.split("\n")))


def _laserfuck_area(program: str) -> int:
    """Return the cells in ``program``'s bounding box: rows times columns.

    A LaserFuck program is a grid the beam travels, so what it costs is the
    rectangle it occupies rather than the characters in it.  The two differ
    because the rows are ragged: a form can hold fewer characters than a
    rival and still need a wider box to run in, and on ``"Hello, World!"``
    the shortest form by ``len`` is nearly twice the grid of the smallest
    one.  Selecting on :func:`len` -- the rule :func:`shortest` names for
    the one-dimensional generators -- would pick that larger grid, which is
    why this metric is the generator's own rather than the shared one.
    """
    return (program.count("\n") + 1) * _laserfuck_columns(program)


def laserfuck(text: str, width: int | None = None) -> str:
    """Build a LaserFuck program that outputs ``text``, the smaller of two.

    Two constructions are available and which wins depends entirely on the
    text.  :func:`_laserfuck_multiply` factors the byte values and adds them
    in base-sized chunks, which is best when they are spread out.
    :func:`_laserfuck_base_ring` counts every cell up to a shared base in one
    loop and then writes only the differences, which is best when they
    cluster -- exactly when the multiply passes stop paying and the other
    form falls back to writing one ``+`` per unit.

    Rather than predict, both are built and the smaller grid is returned --
    smaller by :func:`_laserfuck_area`, the bounding box, not by ``len``.  A
    ``width`` disqualifies a form that cannot meet it; if neither can, the
    multiplying form's own fallback still applies.
    """
    forms = [_laserfuck_multiply(text, width)]
    for factored in (False, True):
        for grouped in (False, True):
            ring = _laserfuck_base_ring(text, factored=factored, grouped=grouped)
            if width is None or _laserfuck_columns(ring) <= width:
                forms.append(ring)
    if width is not None:
        # the snaked form exists only for the bounded case: it spends rows
        # to buy columns, which is a loss when there is no bound to meet
        snake = _laserfuck_snake_ring(text, width)
        if snake is not None:
            forms.append(snake)
    return min(forms, key=_laserfuck_area)


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

    if parts:  # pragma: no cover - the frames the builder emits are balanced
        # An unbalanced frame: keep it whole rather than dropping it.  Every
        # frame this is handed closes its own brackets, so the remainder is
        # always empty; this is what would keep a future unbalanced one from
        # losing its tail silently.
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
