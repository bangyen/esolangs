"""Register text generators."""

from collections.abc import Callable

from esolangs.tools._polynomial import format_coeffs, multiply, primes
from esolangs.tools.generators.helpers import _cm_constants, _require_bytes

__all__ = [
    "albabet",
    "bio",
    "collatz_multiverse",
    "dig",
    "dotlang",
    "eval",
    "huf",
    "polynomial",
    "qoibl",
    "sophie",
    "wii2d",
]


def albabet(text: str) -> str:
    """Build an AlbaBet program that outputs ``text``.

    AlbaBet's accumulator ``x`` starts at 0; ``c`` zeroes it, a run of ``a``
    moves it up to the character's code, and ``i`` prints it.  A ``c`` resets
    ``x`` before each character so the characters are independent.
    """
    _require_bytes(text, "AlbaBet")
    return "".join("c" + "a" * ord(c) + "i" for c in text)


def bio(text: str) -> str:
    """Build a BIO program that outputs ``text``.

    The x register is driven from the previous character's value to the next
    one with ``0ox``/``1ox`` runs (increment/decrement), then printed with
    ``1ix``.
    """
    _require_bytes(text, "BIO")
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


def sophie(text: str) -> str:
    """Build a Sophie program that outputs ``text``.

    Each ``#<char>,`` sets the accumulator to the character's code and prints
    it.  ``$`` would be read as the numeric marker by ``#$``, so a literal
    ``$`` (like a newline) uses the numeric form ``#$<code>,``.
    """
    # "$" would be taken as the numeric marker by "#$", so it uses the
    # numeric form like a newline does.
    return "".join(f"#${ord(c)}," if c in "\n$" else f"#{c}," for c in text)


def dig(text: str) -> str:
    """Build a Dig program that outputs ``text``.

    Each character is a work segment: ``<char>:`` prints the mole's value as
    the character (``%:`` for a space, which reads 0 from the row below).
    ``$`` reads a single-digit segment length from the row below, so a
    segment is flushed every four characters; a segment starting with a digit
    gets one padding cell so it is not read as the count.
    """
    if not all(c == " " or c in ".,!?" or c.isalnum() for c in text):
        raise ValueError("Dig can only output letters, digits, spaces and .,!?")
    # Each "$" reads a single-digit count from the row below, so a segment can
    # drive at most nine work commands: four "c:" pairs (two per character).
    # A segment that starts with a digit would be read as the count instead,
    # so it gets one extra padding cell first.
    row0 = [">"]
    row1 = [" "]
    seg: list[str] = []

    def flush() -> None:
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


def polynomial(text: str) -> str:
    """Build a Polynomial program that outputs ``text``.

    Each character is produced by a ``+=``/``-=`` delta from the previous
    one followed by an output instruction.  The instruction stream is
    encoded as the roots of a polynomial whose zeroes are the instruction
    primes ``p**(2*b)`` shifted by the deltas, so evaluating the polynomial
    at the right roots runs them in order.
    """
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

    return str(format_coeffs(coeffs))


def qoibl(text: str) -> str:
    """Build a Qoibl program that outputs ``text``.

    Each ``tt <bits> tt`` prints the value whose bits encode the character:
    the binary digits are written as ``y`` (1) and ``e`` (0).
    """

    def bits(n: int) -> str:
        return f"{n:b}".replace("0", "e").replace("1", "y")

    return "\n".join(f"tt {bits(ord(c))} tt" for c in text)


def wii2d(text: str) -> str:
    """Build a WII2D program that outputs ``text``.

    For each character, the program moves right to a fresh cell, builds the
    character's code with the cheapest strategy (literal digit, square,
    double, or a combination), prints it with ``~``, and halts with ``.``
    after the last one.  The ``!`` marker on line 2 sets the starting
    direction.
    """

    def build(target: int) -> str:
        best = (float("inf"), "")
        strategies: list[
            tuple[int, int, Callable[[int], int], Callable[[int], str]]
        ] = [
            (1, min(target, 9), lambda d: d, lambda d: f"{d}"),
            (2, round(target**0.5), lambda d: d * d, lambda d: f"{d}s"),
            (2, round(target / 2), lambda d: 2 * d, lambda d: f"{d}*"),
            (3, round((target / 2) ** 0.5), lambda d: 2 * d * d, lambda d: f"{d}s*"),
            (3, round(target / 4), lambda d: 4 * d, lambda d: f"{d}**"),
        ]
        for cost, digit, value, ops in strategies:
            d = max(0, min(9, digit))
            v = value(d)
            total = cost + abs(target - v)
            if total < best[0]:
                adj = target - v
                best = (total, ops(d) + ("+" * adj if adj >= 0 else "-" * -adj))
        return best[1]

    prog = ">" + "".join(build(ord(c)) + "~" for c in text) + "."
    return f"{prog}\n!"


def dotlang(text: str) -> str:
    """Build a single-dot program that prints one backtick-wrapped string.

    The interpreter's backtick match is greedy, so the text must fit on one
    grid row; line-break characters would split the program into rows and a
    backtick would be absorbed by the string match.
    """
    if any(c in "\n\r\v\f\x1c\x1d\x1e\x85`" for c in text):
        raise ValueError("dotlang can only output a single line without backticks")
    return "\u2022#" + "`" + text + "`#"


def huf(text: str) -> str:
    """Each character is a multiply segment ``# +*a | +*b ! +*r >@``.

    ``#`` resets num and mul, a run of ``a`` increments num, ``|`` starts the
    multiplier, a run of ``b`` increments it to ``b + 1``, and ``!`` multiplies
    num by ``mul - 1`` so it becomes ``a * b``; a final run of ``r`` tops it
    up to the character code, then ``>@`` prints it and closes the segment.
    ``a`` is searched near ``sqrt(ord)`` so the program is O(sqrt) rather than
    O(ord).
    """
    return "".join(_huf_segment(ord(c)) for c in text)


def _huf_segment(value: int) -> str:
    best = min(
        (
            (a + b + r, a, b, r)
            for a in range(1, int(value**0.5) + 2)
            for b, r in (divmod(value, a),)
        ),
    )
    _, a, b, r = best
    return "#" + "+" * a + "|" + "+" * b + "!" + "+" * r + ">@"


def eval(text: str) -> str:  # noqa: A001 - the language is named "Eval"
    """Build a program that prints ``text`` as one string literal.

    A double quote inside the text would end the literal early, so it is
    encoded as a backtick, which the interpreter expands back to a quote.
    """
    if "`" in text:
        raise ValueError("eval cannot output a literal backtick")
    if not text:
        return ""
    return '"' + text.replace('"', "`") + '".'


def collatz_multiverse(text: str) -> str:
    """Build a Collatz Multiverse program that outputs ``text``.

    Every line is ``[var1] = [var2] x + [var3], [DO|NOT] PRINT.`` and the
    operands must be variables, so byte values have to be driven into
    registers through the Collatz transform (odd or 0 values become
    ``v*var2+var3``, even values halve).  A constant table of byte values is
    bootstrapped from ``negativeOne`` with the copy trick and parity-aware
    ``one x + one``/``one x + two`` increments; each output character is then
    a single line on a fresh register: ``o = negativeOne x + k<byte>`` copies
    the byte and prints it.
    """
    if not text:
        return ""
    _require_bytes(text, "Collatz Multiverse")
    lines = _cm_constants(max(ord(c) for c in text))
    for i, c in enumerate(text):
        lines.append(f"o{i} = negativeOne x + k{ord(c)}, DO PRINT.")
    return "\n".join(lines)
