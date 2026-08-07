"""Register text generators."""

from esolangs.tools._polynomial import format_coeffs, multiply, primes

__all__ = ['bio', 'dig', 'dotlang', 'eval', 'huf', 'polynomial', 'qoibl', 'sophie', 'wii2d']
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


def sophie(text):
    # "$" would be taken as the numeric marker by "#$", so it uses the
    # numeric form like a newline does.
    return "".join(f"#${ord(c)}," if c in "\n$" else f"#{c}," for c in text)


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
    for (a, b), p in zip(instrs, primes(len(instrs)), strict=True):
        coeffs = multiply(coeffs, [1, -2 * a, a * a + p ** (2 * b)])

    return format_coeffs(coeffs)


def qoibl(text):
    return "\n".join(
        f"tt {bin(ord(c))[2:].replace('0', 'e').replace('1', 'y')} tt" for c in text
    )


def wii2d(text):
    def build(target):
        best = (float("inf"), "")
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
            if total < best[0]:
                adj = target - v
                best = (total, ops(d) + ("+" * adj if adj >= 0 else "-" * -adj))
        return best[1]

    prog = ">" + "".join(build(ord(c)) + "~" for c in text) + "."
    return "\n".join([prog, "!"])


def dotlang(text):
    """A single dot that prints one backtick-wrapped string literal.

    The interpreter's backtick match is greedy, so the text must fit on one
    grid row; line-break characters would split the program into rows and a
    backtick would be absorbed by the string match.
    """
    if any(c in "\n\r\v\f\x1c\x1d\x1e\x85`" for c in text):
        raise ValueError("dotlang can only output a single line without backticks")
    return "\u2022#" + "`" + text + "`#"


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


