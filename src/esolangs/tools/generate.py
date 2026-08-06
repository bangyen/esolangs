import math
import re
import sys


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
    res = ""
    num = 0

    for c in text:
        n = ord(c) + 1
        a = int(n**0.5)
        b = (n // a) * "<"
        tail = (n % a) * ">!"
        num = max(num, a)
        res += f'{a * "!"}{tail}' f"><{b}.!>><>!\n"

    return ">>!" * num + "\n" + res[-1:]


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
    return "".join(f"[PSH INT {ord(c)}][PRT]" for c in text) + "[END]"


def qoibl(text):
    return "\n".join(
        f"tt {bin(ord(c))[2:].replace('0', 'e').replace('1', 'y')} tt" for c in text
    )


def _collatz_trajectory(start):
    values = []
    value = start
    while value > 1:
        values.append(value)
        value = value // 2 if value % 2 == 0 else 3 * value + 1
    return values


_ZTOALC_SEARCH_LIMIT = 2048


def ztoalc(text):
    n = len(text)
    if not text:
        return "2"

    best = None
    candidate = 2
    while candidate < _ZTOALC_SEARCH_LIMIT and (best is None or candidate < best[0]):
        values = _collatz_trajectory(candidate)
        if len(values) >= n:
            cand_size = max(values[:n])
            if best is None or cand_size < best[0]:
                best = (cand_size, candidate)
        candidate += 1

    if best is None:
        # No compact trajectory within the search bound: the power-of-two
        # start always yields a trajectory of length n, so it works for any
        # text, at the cost of a 2**n-line program.
        size = 2**n
        start = size
        values = [size >> k for k in range(n)]
    else:
        size, start = best
        values = _collatz_trajectory(start)[:n]

    lines = [""] * size
    lines[0] = str(start)

    for value, char in zip(values, text):
        lines[value - 1] = f"print {ord(char)}"

    return "\n".join(lines)


_GENERATORS = {
    "BFStack": bfstack,
    "BrainIf": brainif,
    "Container": container,
    "EXCON": excon,
    "Forþ": forth,
    "LaserFuck": laserfuck,
    "Magnitude": magnitude,
    "Modulous": modulous,
    "Painfuck": painfuck,
    "Qoibl": qoibl,
    "Suffolk": suffolk,
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
