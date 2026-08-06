import math
import re
import sys

from esolangs.tools._polynomial import format_coeffs, multiply, primes
from esolangs.tools._ztoalc import _collatz_prefix, _search_start
from esolangs.tools.ztoalc_starts import STARTS


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
    text = text[::-1]
    res = ""

    for c in text:
        o = ord(c)
        n = int(math.log(o, 15))
        m = o // (15**n)
        p = o - m * 15**n

        res += n * "F" + (n - 1) * "*" + s[m] + "*" + s[p] + "+"
    return f"0{res}[.]"


def laserfuck(text):
    data = [*map(ord, text)]
    code = ""

    def get(m):
        s = ""

        for n in data:
            q = n // m
            s += ">" + "+" * q

        return s.rstrip(">")

    while True:
        top = max(data)
        sqr = int(math.sqrt(top))
        end = get(1)

        if not top:
            break

        if all(data):
            sqr = min([sqr, *data])

        ops = get(sqr)
        bck = ops.count(">")

        if bck < 11:
            ops += bck * "<"
        else:
            ops += "[<]>"

        ops = "+" * sqr + f"[{ops}-]"

        diff = len(end) - len(ops) - ops.count("[") * 7

        if diff < 0:
            break

        code += ops
        data = [k % sqr for k in data]

    if "[" not in code:
        return f"\xff}}}}{end}\n|o^\n _ "

    match = re.search(r"\[([^[\]]*)", code)
    loop = match[1] if match else ""
    code = code.replace(loop, "", 1)
    code = code.replace("[]", "[}]")
    frst = code.find("[") + 8

    num = 0
    res = [" }}", "|o^", " _ "]

    for c in code:
        if c == "[":
            top_str = "v }  }"
            bot_str = "}#^)#^"
            num += 1
        elif c == "]":
            top_str = "#/)"
            bot_str = " / "
        else:
            top_str = c
            bot_str = " "

        k: int = 2 - (num == 2)
        res[0] += str(top_str)
        res[3 - k] += str(bot_str)
        res[k] += len(str(top_str)) * " "

        if c == "]":
            num -= 1

    search_match = re.search("}  }v?", res[0])
    search = search_match[0] if search_match else ""
    search_spaces = " " * len(search)
    res[0] = res[0].replace(search, search_spaces, 1)

    rest = len(loop) + frst
    over = len(end) + frst
    over -= len(res[0]) - 2
    half = (max(over, 0) // 2) + 1

    if end:
        res[0] += end[:half] + "^"
        end = end[half:]
        end = f"x{end[::-1]}{{"

        end = end.rjust(len(res[0]))
        res.insert(0, end)
    else:
        res[0] += "x"

    size = len(res[0])
    cntr = 2

    while (rest // cntr) > size:
        cntr += 1

    cntr += cntr % 2
    botm = (rest // cntr) + 1
    lnth = botm + 1

    res.insert(0, f"\xff}}{loop[:lnth]}v")

    for k in range(cntr - 1):
        part = loop[lnth : lnth + botm]
        lnth += botm

        if not k % 2:
            part = part[::-1]
            move = "v{}{{"
        else:
            move = "}}{}v"

        part = part.rjust(botm)
        part = move.format(part)
        res.insert(k + 1, "  " + part)

    spaces: str = " " * (frst - 5)
    beg = f" ^{spaces}{{  {{"

    cntr -= 1
    res[cntr] = res[cntr].replace("  v" + " " * frst, beg + "v ")

    return "\n".join(res)


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
                num = int(math.log(x // 2, 2))
                prog += "s" + num * "m"
                n -= x
            elif y:
                num = int(math.log(y // 3, 2))
                prog += "i" + num * "m"
                n -= y

        if n == 1:
            prog += "ips"
            mode = not mode
        elif n > 2:
            prog += (n // 3) * "i"
            n = n % 3

            if n % 3 == 1:
                prog = prog[:-1]
                n += 3

        prog += (n // 2) * "s" + mode * "p" + "e"
        last = ord(c)
        mode = False

    return prog


def painfuck(text):
    def add(val):
        return (val // 2) * "p" + (val % 2) * "ps"

    def close(val, s, op):
        if val > 7:
            pwr = int(math.log(val, 7))
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
        sqr = int(math.sqrt(val))

        if sqr > 3:
            move = ("rl", "lr")["r" in res]
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

    cyc = ["rwzjkvep", "dlahiqbostcuy"]
    text = res
    res = ""

    for k in range(len(text)):
        for c in cyc:
            if text[k] in c:
                n = c.find(text[k])
                res += c[(n + k) % len(c)]

    return res


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
    res = ""
    last = 0

    for c in text:
        b = bin(ord(c) ^ last)[2:].zfill(8).rstrip("0")
        s = b.replace("0", "2").replace("1", "122")

        if n := len(b):
            res += f"{s[:-2]}" f'{"121" * n}'[:-1] + "\n"
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
    k = 2 * max((ord(c) + 1 for c in text), default=0) + 2
    tokens = ["o"]
    buf: list = []

    for c in text:
        inc = ord(c) + 1
        if inc in (9, 10, 11, 12, 13, 28, 29, 30, 31, 32):
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
    return "".join(f"#${ord(c)}," if c == "\n" else f"#{c}," for c in text)


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
    row0 = [">"]
    row1 = [" "]
    seg: list = []

    def flush():
        if not seg:
            return
        n = len(seg) * 2
        row0.append("$")
        row1.append(str(n % 10))
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
    interpreter expands back to a comma.
    """
    if "\n" in text or "*44" in text or text.startswith("$"):
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
