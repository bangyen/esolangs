import math
import re
import sys

from esolangs.tools._polynomial import format_coeffs, multiply, primes
from esolangs.tools._ztoalc import _collatz_prefix, _search_start
from esolangs.tools.ztoalc_starts import STARTS


def _ilog(base, n):
    """Floor of log_base(n), computed with integers to avoid float error.

    Raises ValueError for non-positive ``n``, like ``int(math.log(n, base))``.
    """
    if n < 1:
        raise ValueError("log of non-positive number")
    k = 0
    while base ** (k + 1) <= n:
        k += 1
    return k


def bfstack(text):
    res = ">\n"
    acc = 0

    for c in text:
        n = ord(c) - acc
        if abs(n) < ord(c) + 3:
            o = "+" if n > 0 else "-"
            res += o * abs(n) + ".\n"
        else:
            o = "+" * ord(c)
            res += f"[-]{o}.\n"
        acc = ord(c)

    return res


def brainif(text):
    res = ""
    acc = 0

    for c in text:
        if (n := ord(c)) < acc:
            res += f"\nif {acc} move right\n"
            for k in range(n):
                res += f"if {k} increment\n"
            res += f"if {n} output\n"
        else:
            res += "\n"
            for k in range(acc, n):
                res += f"if {k} increment\n"
            res += f"if {n} output\n"
        acc = ord(c)

    return res.strip()


def container(text):
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


def forth(text):
    s = "0123456789ABCDEF"
    res = ""

    for c in text[::-1]:
        o = ord(c)
        n = _ilog(15, o)
        m = o // (15**n)
        p = o - m * 15**n

        res += n * "F" + (n - 1) * "*" + s[m] + "*" + s[p] + "+"
    return f"0{res}[.]"


def laserfuck(text):
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

    def chunks(base):
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

    # top row: output-mode byte, the loop start, then a turn down
    grid.insert(0, f"\xff}}{loop[:offset]}v")

    # serpentine rows carry the rest of the loop body around the frame
    for row in range(tracks - 1):
        part = loop[offset : offset + per_row]
        offset += per_row

        if not row % 2:
            part = part[::-1]
            move = "v{}{{"
        else:
            move = "}}{}v"

        grid.insert(row + 1, "  " + move.format(part.rjust(per_row)))

    # connect the last serpentine row back into the frame at the loop entry
    connector = f" ^{' ' * (loop_col - 5)}{{  {{"
    tracks -= 1
    grid[tracks] = grid[tracks].replace("  v" + " " * loop_col, connector + "v ")

    return "\n".join(grid)


def magnitude(text):
    def close(val, start):
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


def painfuck(text):
    def add(val):
        return (val // 2) * "p" + (val % 2) * "ps"

    def close(val, s, op):
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

    def loop(val, s, op):
        sqr = math.isqrt(val)

        if sqr > 3:
            move = "lr" if "r" in res else "rl"
            s += move + add(sqr) + "al"

            if op == "p":
                s += add(sqr)
            else:
                s += sqr * "s"

            s += move + "sbl"
            val -= sqr**2

        return val, s

    res = ""
    last = 0

    for c in text:
        n = ord(c) - last

        if abs(n) > ord(c):
            res += ("rl", "lr")["r" in res]
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


def suffolk(text):
    if not text:
        return ""
    # Cell 2 is a persistent helper large enough that ``!`` (which computes
    # max(0, cell + 1 - acc)) zeroes cells 0 and 1, so they can be reused.
    big = max(int((ord(c) + 1) ** 0.5) for c in text) + 2
    res = []
    for c in text:
        n = ord(c) + 1
        a = max(1, int(n**0.5))
        b, r = divmod(n, a)
        res.append(f">><!>><>!{'!' * a}{'>!' * r}><{'<' * b}.")
    return ">>!" * big + "\n" + "\n".join(res)


def _123(text):
    """A 1/2 program per character, terminated by a trailing 1."""
    res = ""
    last = 0

    for c in text:
        bits = bin(ord(c) ^ last)[2:].zfill(8).rstrip("0")
        encoded = bits.replace("0", "2").replace("1", "122")

        if n := len(bits):
            res += f"{encoded[:-2]}" f'{"121" * n}'[:-1] + "\n"
        else:
            res += "12112\n"
        last = ord(c)

    return res + "1"


def excon(text):
    res = ""

    for c in text:
        bits = format(ord(c), "08b")
        res += ":"
        pos = 7
        for j in range(7, -1, -1):
            if bits[j] == "1":
                res += "<" * (pos - j) + "^"
                pos = j
        res += "!"

    return res


def modulous(text):
    if not text or '"' in text or "[" in text or "]" in text or "\x00" in text:
        return "".join(f"[PSH INT {ord(c)}][PRT]" for c in text) + "[END]"
    return f'[PSH STR "{text}"][PRT STR][JMP B 1 NIF 0]'


def qoibl(text):
    return "\n".join(
        f"tt {bin(ord(c))[2:].replace('0', 'e').replace('1', 'y')} tt" for c in text
    )


def ztoalc(text):
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

    for value, char in zip(values, text):
        lines[value - 1] = f"print {ord(char)}"

    return "\n".join(lines)


def temporary(text):
    # These control/whitespace characters cannot be embedded in the ``*``
    # string literal, so they are output via their own ``v<value>`` token.
    special = (9, 10, 11, 12, 13, 28, 29, 30, 31, 32)
    k = 2 * max((ord(c) + 1 for c in text), default=0) + 2
    tokens = ["o"]
    buf: list = []

    for c in text:
        inc = ord(c) + 1
        if inc in special:
            if buf:
                tokens.append("*" + "".join(buf))
                buf = []
            tokens.append(f"v{inc}")
        else:
            buf.append(chr(inc))

    if buf:
        tokens.append("*" + "".join(buf))
    tokens.append(f"v{k}")

    return " ".join(tokens)


def sophie(text):
    # "$" would be taken as the numeric marker by "#$", so it uses the
    # numeric form like a newline does.
    return "".join(f"#${ord(c)}," if c in "\n$" else f"#{c}," for c in text)


def bio(text):
    res = []
    prev = 0
    for c in text:
        n = ord(c)
        if n > prev:
            res.append("0ox" * (n - prev))
        else:
            res.append("1ox" * (prev - n))
        res.append("1ix")
        prev = n
    return "".join(res)


_PLUS_REM = ["", "62", "6622", "55599", "559", "5"]  # +5/+6 paths for remainders
_MINUS_REM = ["", "95", "9955", "999555", "262", "2"]  # -5/-6 paths


def _six_five_path(src, dst):
    """Shortest sequence of 5/6 additions and 2/9 subtractions from src to dst.

    The delta is built from a run of sixes (or fives) plus a short remainder
    pattern, choosing whichever base yields the shorter program.
    """
    delta = dst - src
    if delta < 0:
        delta = -delta
        q6, r6 = divmod(delta, 6)
        q5, r5 = divmod(delta, 5)
        p6 = "9" * q6 + _MINUS_REM[r6]
        p5 = "2" * q5 + _MINUS_REM[r5]
        return p6 if len(p6) <= len(p5) else p5
    q6, r6 = divmod(delta, 6)
    q5, r5 = divmod(delta, 5)
    p6 = "6" * q6 + _PLUS_REM[r6]
    p5 = "5" * q5 + _PLUS_REM[r5]
    return p6 if len(p6) <= len(p5) else p5


def six_five(text):
    cur = 0
    res = []
    for c in text:
        res.append(_six_five_path(cur, ord(c)))
        res.append("A")
        cur = ord(c)
    return "".join(res)


_ASCII_ART_BLOCKS = {
    "-": "-",
    ".": "#\n#",
    "+": "|\n|\n|\n|\n|",
    "[": "_\n_\n_\n_\n_\n_",
    "]": "|\n|\n|\n|\n|\n|",
}


def ascii_art(text):
    # An empty program still needs a cell; the "+" block is a no-op.
    if not text:
        return _ASCII_ART_BLOCKS["+"]
    bf = "".join("[-]" + "+" * ord(c) + "." for c in text)
    return "\n\n".join(_ASCII_ART_BLOCKS[ch] for ch in bf)


def minifuck(text):
    if "\x00" in text:
        raise ValueError("Minifuck cannot output the NUL character")
    res = []
    tape = [0] * 8
    ptr = 0

    def ensure(index):
        while len(tape) <= index:
            tape.append(0)

    def flip(position):
        nonlocal ptr
        ptr = position + 1
        ensure(ptr + 1)
        tape[ptr] ^= 1
        if not tape[ptr]:
            ensure(ptr + 2)
            tape[ptr + 1] ^= 1

    for c in text:
        bits = [int(b) for b in f"{ord(c):07b}"]
        first = next((k for k in range(1, 8) if tape[k] != bits[k - 1]), None)
        if first is None:
            res.append(".")
            ptr += 1
            ensure(ptr)
            tape[ptr] ^= 1
            continue
        if ptr > first - 1:
            res.append("<" * (ptr - (first - 1)))
            ptr = first - 1
        for k in range(ptr + 1 if ptr < first - 1 else first, 8):
            res.append("[x")
            flip(k - 1)
            if tape[k] != bits[k - 1]:
                res.append("<")
                ptr -= 1
                res.append("[x")
                flip(k - 1)
        res.append(".")
        ptr += 1
        ensure(ptr)
        tape[ptr] ^= 1

    return "".join(res)


def wii2d(text):
    def build(target):
        best = None
        for cost, digit, value, ops in [
            (1, min(target, 9), lambda d: d, lambda d: f"{d}"),
            (2, round(target**0.5), lambda d: d * d, lambda d: f"{d}s"),
            (2, round(target / 2), lambda d: 2 * d, lambda d: f"{d}*"),
            (3, round((target / 2) ** 0.5), lambda d: 2 * d * d, lambda d: f"{d}s*"),
            (3, round(target / 4), lambda d: 4 * d, lambda d: f"{d}**"),
        ]:
            d = max(0, min(9, digit))
            v = value(d)
            total = cost + abs(target - v)
            if best is None or total < best[0]:
                adj = target - v
                best = (total, ops(d) + ("+" * adj if adj >= 0 else "-" * -adj))
        assert best is not None
        return best[1]

    prog = ">" + "".join(build(ord(c)) + "~" for c in text) + "."
    return "\n".join([prog, "!"])


def dig(text):
    if not all(c == " " or c in ".,!?" or c.isalnum() for c in text):
        raise ValueError("Dig can only output letters, digits, spaces and .,!?")
    # Each "$" reads a single-digit count from the row below, so a segment can
    # drive at most nine work commands: four "c:" pairs (two per character).
    # A segment that starts with a digit would be read as the count instead,
    # so it gets one extra padding cell first.
    row0 = [">"]
    row1 = [" "]
    seg: list = []

    def flush():
        if not seg:
            return
        pad = 1 if seg[0][0].isdigit() else 0
        n = pad + len(seg) * 2
        row0.append("$")
        row1.append(str(n))
        if pad:
            row0.append(" ")
        row0.extend(seg)
        row1.extend(" " * n)
        seg.clear()

    for c in text:
        seg.append("%:" if c == " " else f"{c}:")
        if len(seg) == 4:
            flush()
    flush()
    row0.append("@")
    row1.append(" ")

    r0 = "".join(row0)
    r1 = list("".join(row1))
    for idx, ch in enumerate(r0):
        if ch == "%":
            r1[idx] = "0"
    return "\n".join([r0, "".join(r1)])


def polynomial(text):
    instrs = []
    prev = 0
    for c in text:
        delta = ord(c) - prev
        if delta > 0:
            instrs.append([delta, 1])  # +=
        elif delta < 0:
            instrs.append([-delta, 2])  # -=
        instrs.append([0, 1])  # output
        prev = ord(c)

    coeffs = [1]
    for (a, b), p in zip(instrs, primes(len(instrs))):
        coeffs = multiply(coeffs, [1, -2 * a, a * a + p ** (2 * b)])

    return format_coeffs(coeffs)


def clockwise(text):
    """A 1D parity program wrapped around the perimeter of a square.

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
    for (x, y), ch in zip(ring, prog):
        grid[y][x] = ch
    grid[0][n - 1] = "R"
    grid[n - 1][n - 1] = "R"
    grid[n - 1][0] = "R"

    return "\n".join("".join(row) for row in grid)


_MAMMALIAN_WALK = {}


def _mammalian_walk(ptr):
    """SPRINT paths from ``ptr`` for every possible SEED count mod 256.

    SEED gives array ``i`` the first value ``(i + 1) * K``, so a SPRINT from
    array ``q`` jumps the pointer to ``(q + (q + 1) * K) % 23``.  Each entry
    maps a SEED count to the arrays it visits and the step each is first hit.
    """
    if ptr not in _MAMMALIAN_WALK:
        paths = []
        for k in range(256):
            q = ptr
            seen = {}
            for step in range(1, 47):
                q = (q + ((q + 1) * k) % 256) % 23
                if q not in seen:
                    seen[q] = step
            paths.append(seen)
        _MAMMALIAN_WALK[ptr] = paths
    return _MAMMALIAN_WALK[ptr]


def mammalian(text):
    """A SEED/SPRINT walk that reaches the array whose value is the character.

    SEED once so every array's first value is ``(i + 1) * K`` for the running
    SEED count K, letting SPRINT move.  For each character, a run of SEEDs is
    split around the SPRINT walk: the first count is chosen so the walk lands
    on a usable array, the final count so that DIGEST there equals the
    character.  EXCRETE stores the value (an "extra") and clears the
    accumulator for the next character.

    A construction always exists: an even array ``q`` has ``gcd(q+1, 256) == 1``,
    so the value equation ``(q+1) * K == target (mod 256)`` is always solvable,
    and the SPRINT walk from any pointer reaches some even array under some
    SEED count.  The scan below was verified exhaustively over every
    (pointer, SEED count, character) state with no extras, plus random states
    with extras, without ever failing.
    """
    if not text:
        return ""
    k = 1
    ptr = 0
    extras: list[list[int]] = [[] for _ in range(23)]
    prog = ["SEED"]

    for c in text:
        t = ord(c)
        walks = _mammalian_walk(ptr)
        best = None

        for q in range(23):
            target = (t - sum(extras[q])) % 256
            g = math.gcd(q + 1, 256)
            if target % g:
                continue
            base = (target // g) * pow((q + 1) // g, -1, 256 // g) % (256 // g)
            for lift in range(g):
                final = base + lift * (256 // g)
                seeds = (final - k) % 256
                for mid in range(seeds + 1):
                    mid_k = (k + mid) % 256
                    if q in walks[mid_k]:
                        steps = walks[mid_k][q]
                        if best is None or seeds + steps < best[0]:
                            best = (seeds + steps, mid_k, final, steps)
                        break

        if best is None:
            raise ValueError(f"mammalian: cannot build {c!r}")
        _, mid_k, final, steps = best
        dk = (mid_k - k) % 256
        d = (final - mid_k) % 256
        prog += (
            ["SEED"] * dk
            + ["SPRINT"] * steps
            + ["SEED"] * d
            + [
                "DIGEST",
                "PRONOUNCE",
                "EXCRETE",
            ]
        )
        k += dk + d
        for _ in range(steps):
            ptr = (ptr + ((ptr + 1) * mid_k) % 256) % 23
        extras[ptr].append(t % 256)

    return "\n".join(prog)


def huf(text):
    """Each character is ``#`` plus ``ord(c)`` increments, then ``>@``.

    ``#`` resets the value, ``+`` increments it, ``>`` prints it as a
    character and ``@`` closes the segment the interpreter extracts.
    """
    return "".join("#" + "+" * ord(c) + ">@" for c in text)


def eval(text):
    """A string literal that the ``.`` instruction prints.

    A double quote inside the text would end the literal early, so it is
    encoded as a backtick, which the interpreter expands back to a quote.
    """
    if "`" in text:
        raise ValueError("eval cannot output a literal backtick")
    if not text:
        return ""
    return '"' + text.replace('"', "`") + '".'


def dotlang(text):
    """A single dot that prints one backtick-wrapped string literal.

    The interpreter's backtick match is greedy, so the text must fit on one
    grid row; line-break characters would split the program into rows and a
    backtick would be absorbed by the string match.
    """
    if any(c in "\n\r\v\f\x1c\x1d\x1e\x85`" for c in text):
        raise ValueError("dotlang can only output a single line without backticks")
    return "\u2022#" + "`" + text + "`#"


def nevermind(text):
    """A ``print`` command whose arguments are joined without a separator.

    Commas separate arguments, so they are encoded as ``*44``, which the
    interpreter expands back to a comma.  Line breaks would split the program
    into separate lines, so they are rejected too.
    """
    if (
        any(c in "\n\r\v\f\x1c\x1d\x1e\x85" for c in text)
        or "*44" in text
        or text.startswith("$")
    ):
        raise ValueError("nevermind can only print a single line without *44 or $")
    bad = [c for c in text if c.isdigit() and not c.isdecimal()]
    if bad:
        raise ValueError("nevermind cannot print the superscript digits " + repr(bad))
    return "print," + text.replace(",", "*44")


_GENERATORS = {
    "6-5": six_five,
    "ASCII art": ascii_art,
    "BFStack": bfstack,
    "BIO": bio,
    "BrainIf": brainif,
    "Clockwise": clockwise,
    "Container": container,
    "Dig": dig,
    "Dotlang": dotlang,
    "Eval": eval,
    "EXCON": excon,
    "Forþ": forth,
    "huf": huf,
    "LaserFuck": laserfuck,
    "Magnitude": magnitude,
    "MAMMALIAN": mammalian,
    "Minifuck": minifuck,
    "Modulous": modulous,
    "Nevermind": nevermind,
    "Painfuck": painfuck,
    "Polynomial": polynomial,
    "Qoibl": qoibl,
    "Sophie": sophie,
    "Suffolk": suffolk,
    "Temporary": temporary,
    "WII2D": wii2d,
    "ZTOALC": ztoalc,
    "123": _123,
}


def main() -> None:
    """Generate a program that outputs the given text for each supported language."""
    if len(sys.argv) < 2:
        print("usage: python -m esolangs.tools.generate <text>")
        print('example: python -m esolangs.tools.generate "Hello, World!"')
        sys.exit(1)

    text = sys.argv[1]
    for name, gen in _GENERATORS.items():
        print(f"--- {name} ---")
        print(gen(text))


if __name__ == "__main__":
    main()
