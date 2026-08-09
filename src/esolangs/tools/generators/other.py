"""Other text generators."""

import math
import re
from array import array
from functools import cache
from typing import Any

from esolangs.tools.generators.helpers import _ilog
from esolangs.tools.ztoalc_starts import STARTS

__all__ = [
    "_123",
    "clockwise",
    "container",
    "forth",
    "home_row",
    "laserfuck",
    "magnitude",
    "nevermind",
    "nocomment",
    "painfuck",
    "unsquare",
    "ztoalc",
]


def clockwise(text: str) -> str:
    """Build a 1D parity program wrapped around a square's perimeter.

    The turtle walks the ring clockwise, executing one instruction per cell.
    Three corner ``R`` cells turn it, and the final cell walks it back to the
    origin facing right, where it halts.  Each ``;`` outputs ``acc % 2``, so
    ``+`` is emitted only when the accumulator's parity needs to flip.
    """
    prog = ""
    parity = 0
    for c in text:
        for bit in bin(ord(c))[2:].zfill(7):
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


def ztoalc(text: str) -> str:
    """Build a ZTOALC program that outputs ``text``.

    The interpreter runs lines in Collatz-trajectory order from the initial
    value on line 1, so each character is placed on the line its trajectory
    step visits.  A ``start`` whose trajectory has at least ``len(text)``
    steps is chosen (from the committed table, or by search), and the program
    is ``start`` on line 1 plus a ``print <code>`` on each visited line.
    """
    n = len(text)
    if not text:
        return "2"

    start = STARTS.get(n)
    if start is None:
        start = _search_start(n)

    values = _collatz_prefix(start, n)
    size = max(values)

    lines = [""] * size
    lines[0] = str(start)

    for value, char in zip(values, text, strict=False):
        lines[value - 1] = f"print {ord(char)}"

    return "\n".join(lines)


# Collatz support for ``ztoalc``.  The committed ``ztoalc_starts`` table
# covers most text lengths; for lengths it misses, the search helpers below
# find a start whose Collatz trajectory is long enough and has the smallest
# maximum visited value.
_ZTOALC_TABLE_LIMIT = 1_000_000
_ZTOALC_MAX_LIMIT = 10_000_000
_length_table_cache: dict[int, Any] = {}


def _collatz_prefix(start: int, n: int) -> list[int]:
    values: list[int] = []
    value = start
    for _ in range(n):
        values.append(value)
        value = value // 2 if value % 2 == 0 else 3 * value + 1
    return values


def _collatz_length_table(limit: int) -> Any:
    """Compute stopping times for every start up to ``limit``, as unsigned shorts.

    Index ``value`` holds the number of Collatz steps from ``value`` to 1;
    index 1 is 0 and a zero elsewhere means "not yet computed". Chain values
    above ``limit`` are walked through without being stored, keeping the
    table bounded at two bytes per entry.
    """
    lengths = array("H", [0]) * (limit + 1)
    lengths[1] = 0

    for start in range(2, limit + 1):
        if lengths[start]:
            continue

        path = []
        value = start
        while value > 1 and (value > limit or not lengths[value]):
            path.append(value)
            value = value // 2 if value % 2 == 0 else 3 * value + 1

        length = lengths[value] if value <= limit else 0
        for value in reversed(path):
            length += 1
            if value <= limit:
                lengths[value] = length

    return lengths


def _collatz_lengths(limit: int) -> Any:
    if limit not in _length_table_cache:
        _length_table_cache[limit] = _collatz_length_table(limit)
    return _length_table_cache[limit]


def _search_start(n: int) -> int:
    """Best start for a text length the committed table does not cover."""
    best: tuple[int, int] | None = None
    limit = _ZTOALC_TABLE_LIMIT
    lengths = _collatz_lengths(limit)
    candidate = _ZTOALC_TABLE_LIMIT

    while candidate <= _ZTOALC_MAX_LIMIT:
        if candidate > limit:
            limit = min(limit * 2, _ZTOALC_MAX_LIMIT)
            lengths = _collatz_lengths(limit)
            continue
        if best is not None and candidate >= best[0]:
            break
        if lengths[candidate] >= n:
            cand_size = max(_collatz_prefix(candidate, n))
            if best is None or cand_size < best[0]:
                best = (cand_size, candidate)
        candidate += 1

    if best is None:
        raise ValueError(
            f"no Collatz start with a trajectory of length {n} within the search limit"
        )
    return best[1]


def forth(text: str) -> str:
    """Each character is built as ``m * 15**n + p`` and printed with ``.``.

    ``F`` pushes 15 (the largest digit), ``*`` and ``+`` do arithmetic, and
    ``.`` prints the top of the stack as a character.  Characters are pushed
    in reverse and a ``[.]`` loop prints them, stopping at the seed 0; a NUL
    would stop that loop, so text containing one is printed with an explicit
    ``.`` per character instead.
    """
    s = "0123456789ABCDEF"

    def build(c: str) -> str:
        o = ord(c)
        if o == 0:
            return "0"
        n = _ilog(15, o)
        m = o // (15**n)
        p = o - m * 15**n
        return n * "F" + (n - 1) * "*" + s[m] + "*" + s[p] + "+"

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
    """Build a Magnitude program that outputs ``text``.

    Each character is produced as a delta from the previous one.  ``s`` and
    ``i`` scale toward powers of 2 and 3, ``p`` flips the sign, ``e`` prints
    the accumulated magnitude as a byte, and a leading ``'`` resets to an
    absolute (non-delta) encoding when the delta would overshoot the target.
    """

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
    """
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

    NoComment's ``c`` zeroes the current cell, ``i`` increments it, and ``o``
    prints it as a byte, so each character becomes a fixed ``c`` + ``i``*N + ``o``
    run.
    """
    return "".join("c" + "i" * ord(c) + "o" for c in text)


def unsquare(text: str) -> str:
    """Generate an Unsquare program that outputs ``text``.

    ``OA``/``IA`` push 0/1 and ``A`` loads it into the accumulator, ``+``
    adds 2, and ``x`` doubles, so each character is built from a parity seed
    (``O`` for even, ``I`` for odd) followed by the shortest ``+``/``x``
    program to the code: doubling makes even values O(log n), with ``+`` runs
    covering the rest.  ``P`` pushes the accumulator and ``o`` prints it.
    """

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

    ``a`` increments the current cell and ``k`` prints it as a byte, resetting
    it to zero (the spec's 5x5 grid initializes at zero). A leading ``as``
    (net zero) keeps NUL characters from collapsing the adjacent ``k``s.
    """
    res = []
    for c in text:
        if ord(c) == 0:
            res.append("ask")
        else:
            res.append("a" * ord(c) + "k")
    return "".join(res) + ";"


def taglate(text: str) -> str:
    """Generate a Taglate program that outputs ``text``.

    The first line seeds the queue with the text itself, and one ``i`` per
    character pops and prints it.  A newline cannot appear in the text
    because it would split the queue line.
    """
    if any(c in "\n\r" for c in text):
        raise ValueError("Taglate cannot output a newline (the queue is one line)")
    return text + "\n" + "i" * len(text)
