"""Other text generators.

laserfuck and streetcode each own a file: their constructions (a laid-out
grid, a walled and folded street) dwarf the rest of the category.  They are
re-exported here so this module stays the import site the package and tests
already use.
"""

import math
from collections import Counter, deque
from functools import cache

from esolangs.tools.text.helpers import (
    _factor_triple,
    _ilog,
    _literal_chunks,
    _require_ascii,
    _require_bytes,
    delta_program,
    run_step,
)
from esolangs.tools.text.laserfuck import laserfuck
from esolangs.tools.text.streetcode import streetcode
from esolangs.tools.wrap import shortest
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

    The *weave* (:func:`_clockwise_weave`) serpentines through the interior
    and runs over 90% code.  A bare *ring* -- code on the perimeter only,
    the interior left dead -- was built alongside it and the shorter won,
    but the ring only ever won on one-character text, and by at most 1.26x:
    a program of ``c`` cells costs it a square of side about ``c / 4``, so
    anything longer is better than 97% blank.  It is not worth a second
    layout, and the weave is now the only shape.

    ``width`` bounds the columns, down to ``_WEAVE_MIN_WIDTH``: the weave
    needs a home lane, a hairpin ladder and two descent lanes, so four
    columns is the narrowest grid the turtle can walk -- the lanes
    themselves carry instructions wherever the walk crosses them once, so
    no separate body column is required.  A smaller
    width is met with that narrowest weave rather than refused, the way
    Streetcode answers a width no shape fits with its narrowest shape.  A
    width is a preference about layout, and a program two columns wider
    than asked is more use to a caller than an exception.
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

    # Clamped, not refused: below the floor the weave has no narrower shape
    # to offer, so the floor itself is the answer.
    if width is not None:
        width = max(width, _WEAVE_MIN_WIDTH)
    folded = _clockwise_weave(prog, width)
    if folded is None:  # pragma: no cover - the floor always admits a weave
        raise AssertionError("no weave at _WEAVE_MIN_WIDTH")
    return folded


# A weave's turning cells: the hairpin ladder in column 1, the two descent
# lanes on the right, and the corners.  Everything else is a slot.
_WEAVE_LANES = "0110"

# The narrowest weave: the home lane, the hairpin ladder, and the two descent
# lanes.  No body column is needed -- at ``body = 0`` the descent lanes and the
# ladder still cross cells the walk visits exactly once, so a four-wide grid
# holds instructions (eleven of them per four-row group) and closes.
_WEAVE_MIN_WIDTH = 4


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
    else:  # pragma: no cover - every grid searched halts or leaves first
        # A walk that neither halts nor leaves would cycle, and no grid over
        # the turn and accumulator characters was found that does: the
        # budget is a guard against one existing, not a path taken.
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

    Returns ``None`` when no weave fits within ``width``.  The caller never
    sees that: it clamps ``width`` up to ``_WEAVE_MIN_WIDTH`` first, which
    always admits a weave.
    """
    best: str | None = None
    limit = width if width is not None else len(prog) + _WEAVE_MIN_WIDTH
    if limit < _WEAVE_MIN_WIDTH:
        return None
    for body in range(0, limit - 3):
        units = 1
        while True:
            grid = _weave_template(units, body)
            slots = _weave_slots(grid)
            if slots is None:  # pragma: no cover - every template so far closes
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
            if units > len(prog):  # pragma: no cover - slots outgrow the program
                # Each unit adds about six slots, so a template holds the
                # program long before this; it stops a runaway search rather
                # than ending a real one.
                break
    return best


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
    return delta_program(text, run_step("i", "d"), "o")


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
        # The band is connected, so the queue never empties first: over every
        # (start, value) pair the generator can ask for, the search either
        # finds a run or the parity guard above rejects it.
        return None  # pragma: no cover - unreachable, see above

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
            if chain is not None:
                # The seed goes first: it is the construction that always
                # exists, so a tie keeps it and the chain has to be strictly
                # shorter to displace it.
                best = shortest(best, chain)
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
    return shortest(absolute, magnitude(text))


def basicfuck(text: str) -> str:
    """Build a Basicfuck program that outputs ``text``.

    One variable ``a`` tracks the current byte: ``+=``/``-=`` walk it to each
    character (within the declared ``0..255`` range) and ``write <- a ;``
    prints it.  ``o=nearest`` pins any accidental overshoot back to the range.
    """
    _require_bytes(text, "Basicfuck")
    return delta_program(
        text,
        lambda cur, target: (
            f"a += {target - cur};\n" if target >= cur else f"a -= {cur - target};\n"
        ),
        "write <- a ;\n",
        prologue="#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n",
    )


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
