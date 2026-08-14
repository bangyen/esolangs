"""Other text generators."""

import math
import re
from functools import cache

from esolangs.tools.generators.helpers import _ilog, _require_ascii, _require_bytes
from esolangs.tools.ztoalc_starts import ANCHORS

__all__ = [
    "_123",
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
    "nevermind",
    "nocomment",
    "painfuck",
    "pct_squared_minus_one",
    "sbleq",
    "three_x",
    "two_d_fish",
    "unsquare",
    "ztoalc",
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


def clockwise(text: str) -> str:
    """Build a 1D parity program wrapped around a square's perimeter.

    The turtle walks the ring clockwise, executing one instruction per cell.
    Three corner ``R`` cells turn it, and the final cell walks it back to the
    origin facing right, where it halts.  Each ``;`` outputs ``acc % 2``, so
    ``+`` is emitted only when the accumulator's parity needs to flip.
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

    n = max(3, (len(prog) + 10) // 4)
    ring = [(i, 0) for i in range(n - 1)]
    ring += [(n - 1, i) for i in range(1, n - 1)]
    ring += [(i, n - 1) for i in range(n - 2, 0, -1)]
    ring += [(0, i) for i in range(n - 2, 0, -1)]

    grid = [[" "] * n for _ in range(n)]
    for (x, y), ch in zip(ring, prog, strict=False):
        grid[y][x] = ch
    grid[0][n - 1] = "R"
    grid[n - 1][n - 1] = "R"
    grid[n - 1][0] = "R"

    return "\n".join("".join(row) for row in grid)


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
        res = (
            "A:\n"
            "+1 EXIT>=1\n\n"
            "PRINT:\n"
            "+1 PRINT<=0\n"
            "-1 PRINT>=1\n\n"
            "OUT:\n"
        )
    else:
        return "EXIT=1:\n" "-1 EXIT>=0"

    for c in text:
        if (o := ord(c) - last) >= 0:
            res += f"+{o} A>={ind}\n" f"-{o} A>={ind + 1}\n"
        else:
            res += f"-{-o} A>={ind}\n" f"+{-o} A>={ind + 1}\n"
        last = ord(c)
        ind += 2

    res += "EXIT=1:\n" f"-1 A>={ind - 2}"

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


def ztoalc(text: str) -> str:
    """Build a ZTOALC program that outputs ``text``.

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


def laserfuck(text: str) -> str:
    """Build a LaserFuck program that outputs ``text``.

    Phase 1 generates a brainfuck-style program: each pass picks a base about
    the square root of the largest remaining value, emits a ``+[>+...+<-]``
    loop that adds each value's base-aligned chunk, then reduces the values by
    that base.  Phase 2 lays the program onto the grid, with the first loop's
    body wrapped around a serpentine track on the edges so the laser travels
    around it.
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
        return f"\xff}}}}{fallback}\n|o^\n _ "

    # -- lay the program out onto the grid --
    match = re.search(r"\[([^[\]]*)", code)
    loop = match[1] if match else ""
    frame = code.replace(loop, "", 1).replace("[]", "[}]")
    loop_col = frame.find("[") + 8  # grid column of the loop's opening bracket

    # build the three frame rows; brackets also place mirror cells beside them
    grid = [" }}", "|o^", " _ "]
    depth = 0

    for c in frame:
        if c == "[":
            top_cell, bottom_cell, depth = "v }  }", "}#^)#^", depth + 1
        elif c == "]":
            top_cell, bottom_cell = "#/)", " / "
        else:
            top_cell, bottom_cell = c, " "

        pad_row = 2 - (depth == 2)  # a nested loop also uses the middle row
        grid[0] += top_cell
        grid[3 - pad_row] += bottom_cell
        grid[pad_row] += " " * len(top_cell)

        if c == "]":
            depth -= 1

    # the "[" marker's stub is a placeholder; blank it out and let the loop
    # track connect back into the frame at ``loop_col`` instead
    entry_match = re.search("}  }v?", grid[0])
    entry = entry_match[0] if entry_match else ""
    grid[0] = grid[0].replace(entry, " " * len(entry), 1)

    track_len = len(loop) + loop_col
    overhang = len(fallback) + loop_col - (len(grid[0]) - 2)
    prefix = (max(overhang, 0) // 2) + 1  # fallback chars that fit on the top row

    if fallback:
        grid[0] += fallback[:prefix] + "^"
        remainder = fallback[prefix:]
        end_row = f"x{remainder[::-1]}{{"
        grid.insert(0, end_row.rjust(len(grid[0])))
    else:
        grid[0] += "x"  # no fallback: the frame ends by killing the laser

    width = len(grid[0])
    tracks = 2

    # enough serpentine rows to hold the loop body around the frame
    while (track_len // tracks) > width:
        tracks += 1

    tracks += tracks % 2  # even, so the serpentine joins back on the left
    per_row = (track_len // tracks) + 1
    offset = per_row + 1

    if len(loop) <= offset or tracks > 2:
        # a loop body that fits on the top row, or a grid too narrow for the
        # serpentine's return path to connect, cannot route the laser back
        # through the body; emit the linear program instead
        return f"\xff}}}}{linear}\n|o^\n _ "

    # top row: output-mode byte, the loop start, then a turn down
    grid.insert(0, f"\xff}}{loop[:offset]}v")

    # serpentine rows carry the rest of the loop body around the frame;
    # tracks is always 2 here (narrower grids fall back to the linear program)
    for row in range(tracks - 1):
        part = loop[offset : offset + per_row]
        offset += per_row
        grid.insert(row + 1, "  v" + part[::-1].rjust(per_row) + "{")

    # connect the last serpentine row back into the frame at the loop entry
    connector = f" ^{' ' * (loop_col - 5)}{{  {{"
    tracks -= 1
    grid[tracks] = grid[tracks].replace("  v" + " " * loop_col, connector + "v ")

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


def _123(text: str) -> str:
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
            res += walk[:-2] + march[:-1] + "\n"
        else:
            res += "12112\n"  # no difference: just march esi up and output
        last = ord(c)

    return res + "1"


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
    adds 2, and ``x`` doubles, so each character is built from a parity seed
    (``O`` for even, ``I`` for odd) followed by the shortest ``+``/``x``
    program to the code: doubling makes even values O(log n), with ``+`` runs
    covering the rest.  ``P`` pushes the accumulator and ``o`` prints it.
    """
    _require_bytes(text, "Unsquare")

    @cache
    def build(start: int, v: int) -> str:
        if v == start:
            return ""
        if v < start:
            return ""
        options = [build(start, v - 2) + "+"]
        if v % 2 == 0:
            options.append(build(start, v // 2) + "x")
        return min(options, key=len)

    def seg(v: int) -> str:
        init = "I" if v % 2 else "O"
        start = v % 2
        return init + "A" + build(start, v)

    return "".join(seg(ord(c)) + "Po" for c in text)


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
        best = min(
            (
                (a + b + r, a, b, r)
                for a in range(1, int(value**0.5) + 2)
                for b, r in (divmod(value, a),)
            ),
        )
        _, a, b, r = best
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


def two_d_fish(text: str) -> str:
    """Build a 2dFish program that outputs ``text``.

    A single row heading right (``/``) carries an accumulator: ``i`` and ``d``
    move it toward each character and ``a`` prints it as a byte.  ``@`` halts.
    """
    _require_bytes(text, "2dFish")
    acc = 0
    res = ["/"]
    for c in text:
        t = ord(c)
        res.append("i" * (t - acc) if t >= acc else "d" * (acc - t))
        res.append("a")
        acc = t
    return "".join(res) + "@"


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


def three_x(text: str) -> str:
    """Build a 3x program that outputs ``text``.

    ``[`` prints the literal up to the next ``]`` and skips past it, so the
    program is ``[text]``; a ``]`` in the text would end the literal early.
    """
    if "]" in text:
        raise ValueError("3x cannot output ']' (it would end the literal)")
    return "[" + text + "]"


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
