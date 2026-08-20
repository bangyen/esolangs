"""Register text generators."""

from collections.abc import Callable

from esolangs.tools._polynomial import format_coeffs, multiply, primes
from esolangs.tools.text.helpers import (
    _cm_constants,
    _require_bytes,
)

__all__ = [
    "addsubjump",
    "bio",
    "collatz_multiverse",
    "decleq",
    "dig",
    "dotlang",
    "eval",
    "polynomial",
    "qoibl",
    "sophie",
    "wii2d",
]


def bio(text: str) -> str:
    """Build a BIO program that outputs ``text``.

    Each character is a signed delta from the previous one, folded mod 256
    into a fresh ``x`` counter and accumulated into ``y``: ``0ox`` sets the
    count ``b``, ``0ix`` enters a loop that runs while ``x`` is nonzero, the
    body ``1ox``/``0oy``*a decrements the counter and adds ``a`` to ``y``,
    ``}`` jumps back, and ``0oy``*r tops up the remainder before ``1iy``
    prints ``y``.  ``a`` and ``b`` are searched so ``a * b + r`` is the
    delta (mod 256) with the shortest runs, keeping the program near
    O(sqrt) rather than O(delta).
    """
    _require_bytes(text, "BIO")
    res = []
    value = 0  # register y, mod 256
    for c in text:
        target = ord(c)
        delta = (target - value) % 256
        if delta == 0:
            res.append("1iy")
            continue
        best = (float("inf"), 1, 0, 0)
        for total in (delta, delta + 256):
            for a in range(1, 256):
                b, r = divmod(total, a)
                if a + b + r < best[0]:
                    best = (a + b + r, a, b, r)
        _, a, b, r = best
        res.append("0ox" * b + "0ix" + "1ox" + "0oy" * a + "}" + "0oy" * r + "1iy")
        value = target
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
    ``v*var2+var3``, even values halve).  A constant table builds each byte
    the text references with a two-line multiply-add (copy an odd constant
    with ``v = negativeOne x + b``, then ``v = a x + c`` makes it
    ``b * a + c``), so only the used bytes are built rather than a full
    ``1..maxval`` chain; each output character is then a single line on a
    fresh register: ``o = negativeOne x + k<byte>`` copies the byte and
    prints it.
    """
    if not text:
        return ""
    _require_bytes(text, "Collatz Multiverse")
    lines = _cm_constants(ord(c) for c in text)
    for i, c in enumerate(text):
        lines.append(f"o{i} = negativeOne x + k{ord(c)}, DO PRINT.")
    return "\n".join(lines)


def addsubjump(text: str) -> str:
    """Build an AddSubJump program that outputs ``text``.

    The program is a self-modifying memory: each instruction occupies four
    cells (``a b c d``) and means ``*a += *b`` (when ``*d <= 0``) or
    ``*a -= *b`` (when ``*d > 0``), then ``goto *c``.  Each character is
    built into a shared ``val`` cell and printed: ``val = val - val`` zeroes
    it (``d = -6`` reads the constant 1, so the subtract branch fires),
    ``val = 1`` seeds it, and a walk down the byte's binary expansion doubles
    it in place (``val = val + val``) and adds 1 for each set bit, then
    ``-1 val c -7`` writes it to I/O.  The doubling makes the program
    O(log byte) rather than O(byte).  Every instruction except the last
    jumps to the next through a data cell holding its address; the final
    print uses ``c = -8`` so it jumps to the constant -1, a special address,
    and halts.
    """
    if not text:
        return ""
    _require_bytes(text, "AddSubJump")
    ops: list[tuple[str, int]] = []
    for char in text:
        ops.append(("zero", -6))  # val = val - val, from the constant 1
        if ord(char):
            ops.append(("inc", -7))  # val = 1
            for bit in bin(ord(char))[3:]:
                ops.append(("dbl", -7))  # val = val + val
                if bit == "1":
                    ops.append(("inc", -7))
        ops.append(("out", -7))
    n = len(ops)
    data_base = 4 * n
    val = data_base + n
    mem: list[int] = []
    for i, (kind, d) in enumerate(ops):
        c = -8 if i == n - 1 else data_base + i
        if kind == "out":
            mem.extend([-1, val, c, -7])
        else:
            mem.extend([val, val if kind in ("zero", "dbl") else -6, c, d])
    for i in range(n - 1):
        mem.append(4 * (i + 1))
    return " ".join(map(str, mem))


def decleq(text: str) -> str:
    """Build a Decleq program that outputs ``text``.

    Each character's byte value is placed in a data cell of the
    self-modifying memory, and one ``-2 cell 0`` instruction per character
    prints it and falls through (the memory-mapped output does not jump).  A
    trailing ``0 0 <past-the-end>`` decrements cell 0 and jumps past the end
    of memory to halt.
    """
    if not text:
        return ""
    _require_bytes(text, "Decleq")
    n = len(text)
    data_base = 3 * n + 3
    mem: list[int] = []
    for i in range(n):
        mem.extend([-2, data_base + i, 0])
    mem.extend([0, 0, 4 * n + 3])  # halt: decrement cell 0, jump past the end
    mem.extend(ord(c) for c in text)
    return " ".join(map(str, mem))
