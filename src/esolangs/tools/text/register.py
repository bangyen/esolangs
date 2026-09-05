"""Register text generators."""

from collections.abc import Callable

from esolangs.tools._polynomial import format_coeffs, multiply, primes
from esolangs.tools.text.helpers import (
    _cm_constants,
    _literal_chunks,
    _require_bytes,
)

__all__ = [
    "addsubjump",
    "bio",
    "collatz_multiverse",
    "decleq",
    "dig",
    "eval",
    "polynomial",
    "qoibl",
    "sophie",
    "wii2d",
]


def bio(text: str) -> str:
    """Build a BIO program that outputs ``text``.

    Each character is a signed delta from the previous one, folded mod 256
    into a fresh ``x`` counter and accumulated into ``y``: ``0ox;`` sets the
    count ``b``, ``0ix{`` enters a loop that runs while ``x`` is nonzero,
    the body ``1ox;``/``0oy;``*a decrements the counter and adds ``a`` to
    ``y``, ``};`` jumps back, and ``0oy;``*r tops up the remainder before
    ``1iy;`` prints ``y``.  ``a`` and ``b`` are searched so ``a * b + r`` is
    the delta (mod 256) with the shortest runs, keeping the program near
    O(sqrt) rather than O(delta).

    Every command carries the ``;`` the wiki ends one with, and a loop-open
    carries the ``{`` that opens its body, so the program is BIO as the
    wiki writes it rather than the bare triples the interpreter used to
    accept.
    """
    _require_bytes(text, "BIO")
    res = []
    value = 0  # register y, mod 256
    for c in text:
        target = ord(c)
        delta = (target - value) % 256
        if delta == 0:
            res.append("1iy;")
            continue
        best = (float("inf"), 1, 0, 0)
        for total in (delta, delta + 256):
            for a in range(1, 256):
                b, r = divmod(total, a)
                if a + b + r < best[0]:
                    best = (a + b + r, a, b, r)
        _, a, b, r = best
        res.append(
            "0ox;" * b + "0ix{" + "1ox;" + "0oy;" * a + "};" + "0oy;" * r + "1iy;"
        )
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


def _dig_segments(text: str, per_segment: int = 4) -> list[tuple[str, str]]:
    """Cut ``text`` into work segments, each a ``(commands, depths)`` pair.

    A segment is ``$`` followed by up to ``per_segment`` ``<char>:`` pairs,
    and the ``$`` reads its length as a single digit from the cell below --
    so a segment can drive at most nine work commands, which is four pairs.
    A segment whose first character is a digit gets one padding cell, or the
    digit would be read as the count instead of the ``$``'s own.

    The two strings of a pair are the same length, so a caller can stack
    them and keep the columns aligned however it lays the segments out.
    """
    segments: list[tuple[str, str]] = []

    def flush(seg: list[str]) -> None:
        if not seg:
            return
        pad = 1 if seg[0][0].isdigit() else 0
        n = pad + len(seg) * 2
        commands = "$" + " " * pad + "".join(seg)
        depths = str(n) + " " * (len(commands) - 1)
        # A "%" reads its 0 from directly below, so the depth row carries one
        # under each; every other depth cell stays blank.
        depths = "".join(
            "0" if commands[i] == "%" else ch for i, ch in enumerate(depths)
        )
        segments.append((commands, depths))

    seg: list[str] = []
    for c in text:
        seg.append("%:" if c == " " else f"{c}:")
        if len(seg) == per_segment:
            flush(seg)
            seg = []
    flush(seg)
    return segments


def dig(text: str, width: int | None = None) -> str:
    """Build a Dig program that outputs ``text``.

    Each character is a work segment: ``<char>:`` prints the mole's value as
    the character (``%:`` for a space, which reads 0 from the row below).
    ``$`` reads a single-digit segment length from the row below, so a
    segment is flushed every four characters; a segment starting with a digit
    gets one padding cell so it is not read as the count.

    ``width`` folds those segments over several row pairs instead of one
    long pair (:func:`_dig_fold`).  Below the narrowest width a fold can
    turn in, the program is stood on end instead and runs down two columns
    (:func:`_dig_vertical`), so a width is always answered with a program
    rather than refused.
    """
    if not all(c == " " or c in ".,!?" or c.isalnum() for c in text):
        raise ValueError("Dig can only output letters, digits, spaces and .,!?")
    if width is not None:
        if width < _DIG_MIN_WIDTH:
            return _dig_vertical(text)
        return _dig_fold(text, width)

    segments = _dig_segments(text)
    r0 = ">" + "".join(commands for commands, _ in segments) + "@"
    r1 = " " + "".join(depths for _, depths in segments) + " "
    # The depth row is built to the command row's width so the two stay
    # column-aligned, but blanks past its last digit are never read; trim
    # them so the emitted program ends where its commands do.
    return "\n".join([r0, r1.rstrip()])


# A folded row needs the heading in column 0, a segment of ``$`` and one
# ``c:`` pair, and the turn column that ends it.  A segment whose character
# is a digit takes its pad cell past that, so such a row comes out one column
# wider than asked rather than the floor being raised for every text.  Below
# this the program is stood on end instead -- see :func:`_dig_vertical`.
_DIG_MIN_WIDTH = 5


def _dig_vertical(text: str) -> str:
    """Stand the whole program on end, two columns wide.

    The mole is turned south by a ``'`` and simply falls through the
    program: every command that ran left-to-right along a row now runs
    top-to-bottom down column 0, and the segment is as atomic as it ever
    was, since falling through it consumes the cells in the same order.

    Column 1 carries the digits.  Dig's ``_value`` reads a digit from
    *any* neighbouring cell rather than specifically the one below, so a
    count beside its ``$`` is found exactly as one under it was, and the
    ``%`` that prints a space reads its ``0`` the same way.  This is also
    why the vertical form needs no padding cell: the count never shares the
    column its segment's characters run down, so a leading digit cannot be
    mistaken for it.

    Two columns is the floor of the language rather than of a layout -- one
    for the commands, one for the digits they read -- so nothing narrower is
    offered and a width below it gets this.
    """
    rows = ["'"]
    for commands, depths in _dig_segments(text):
        for index, char in enumerate(commands):
            digit = depths[index] if index < len(depths) else " "
            rows.append(char + digit.rstrip())
    rows.append("@")
    return "\n".join(rows)


def _dig_fold(text: str, width: int) -> str:
    """Fold ``text``'s segments into rows ``width`` columns wide.

    Every content row runs *rightward*, the way the unfolded program does,
    and a blank return lane below each pair carries the mole back to the
    left margin.  Each row states its own heading rather than inheriting
    one -- ``>`` opens a command row and ``'`` turns the mole down at the
    end of it -- which is the same reason WII2D's serpentine spells out
    every turn: no row depends on the heading the previous one ended with.

    A true boustrophedon would cost the same three rows per pair, since a
    leftward command row still needs a spacer between it and the depth
    digits above it.  The return lane is preferred because it doubles as
    that spacer: ``$`` and ``%`` read a digit from *any* adjacent cell, and
    Dig's ``_value`` scans upward first, so a command row must never
    sit directly beneath another pair's depth digits.  Running every row
    rightward also keeps each segment's cells in the one order.

    A segment is never split across rows: while a ``$`` count is running,
    every cell is consumed as a work command, so a turn character inside
    one would be eaten as a command rather than steering the mole.  Segments
    are therefore sized to the row, and narrow widths simply carry fewer
    ``c:`` pairs per ``$``.
    """
    # Column 0 holds the heading and the last column the turn, so a segment
    # has the columns between them.  Each "c:" pair is two cells past the
    # "$" and its worst-case pad.
    room = width - 2
    per_segment = max(1, min(4, (room - 2) // 2))
    segments = _dig_segments(text, per_segment)

    # A segment carrying a pad cell is one column wider than ``room`` was
    # sized for, and the turn has to stay clear of it: the rows are laid out
    # to whichever is wider, so a padded segment gives every row one more
    # column rather than pushing its own turn off the end.
    span = max([room, *(len(c) for c, _ in segments)])

    rows: list[str] = []
    line: list[tuple[str, str]] = []

    def emit(*, last: bool) -> None:
        """Write the packed segments as a command row, depths, and a lane.

        A row is padded out to ``span`` only while more rows follow, so the
        turns stay in one column; the last row stops at its own commands
        rather than trailing filler out to a width it never needed.
        """
        commands = "".join(c for c, _ in line)
        depths = "".join(d for _, d in line)
        tail = "@" if last else "'"
        body = commands if last else commands.ljust(span)
        rows.append(">" + body + tail)
        rows.append(" " + depths.ljust(len(body)) + " ")
        if not last:
            # The row's trailing "'" turns the mole down, and it falls past
            # the depth row into the lane's "<" and walks west.  The "'" in
            # column 0 turns it down again, onto the next row's own ">".
            rows.append("'" + " " * span + "<")

    for commands, depths in segments:
        if line and sum(len(c) for c, _ in line) + len(commands) > span:
            emit(last=False)
            line = []
        line.append((commands, depths))
    emit(last=True)
    return "\n".join(row.rstrip() for row in rows)


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


def wii2d(text: str, width: int | None = None) -> str:
    """Build a WII2D program that outputs ``text``.

    For each character, the program moves right to a fresh cell, builds the
    character's code with the cheapest strategy (literal digit, square,
    double, or a combination), prints it with ``~``, and halts with ``.``
    after the last one.  The ``!`` marker on line 2 sets the starting
    direction.

    ``width`` folds the instruction line into a boustrophedon grid; see
    :func:`_wii2d_serpentine`.
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
    if width is not None:
        # Narrower than a row can hold is answered with the narrowest grid
        # that can, rather than with the unfolded line: that line is the
        # widest form there is, so ignoring the width would widen the very
        # program the caller asked to narrow.
        return _wii2d_serpentine(prog, max(width, _WII2D_MIN_WIDTH))
    return f"{prog}\n!"


# Each serpentine row spends one cell on the heading that starts it and one
# on the ``v`` that drops to the next, so a narrower grid has no room for
# any instruction between them.
_WII2D_MIN_WIDTH = 3


def _wii2d_serpentine(prog: str, width: int) -> str:
    """Fold ``prog`` into a boustrophedon ``width`` columns wide.

    Every row states its own heading rather than inheriting one: an even row
    is ``>{group}v`` (driven East, then dropped) and an odd row is
    ``v{group[::-1]}<`` (driven West, so the group is written reversed).
    Because each turn is spelled out, no fold depends on the velocity the
    previous row happened to end with.

    The ``!`` marker goes directly *below* the first instruction row: the
    interpreter starts the pointer one cell above the marker heading north,
    so that lands it on row 0, whose leading ``>`` immediately turns it
    East.  (Putting the marker on top instead starts the pointer at row
    ``-1``, which wraps to the *last* row and runs the program's tail.)

    The trailing ``v`` on the final row is unreachable: ``prog`` ends with
    the halting ``.``, which fires before the pointer can reach it.
    """
    body = width - 2
    groups = [prog[i : i + body] for i in range(0, len(prog), body)]
    rows = [
        (
            ">" + group.ljust(body) + "v"
            if n % 2 == 0
            else "v" + group[::-1].rjust(body) + "<"
        )
        for n, group in enumerate(groups)
    ]
    return "\n".join([rows[0], "!", *rows[1:]])


def eval(  # noqa: A001 - the language is named "Eval"
    text: str, width: int | None = None
) -> str:
    """Build a program that prints ``text`` as one string literal.

    A double quote inside the text would end the literal early, so it is
    encoded as a backtick, which the interpreter expands back to a quote.

    A ``width`` splits the text across several ``"..."``.  literals, one per
    line; each prints in turn, so the output is unchanged.  The literal
    itself cannot be reflowed, since a newline between the quotes is a
    character the program would print.
    """
    if "`" in text:
        raise ValueError("eval cannot output a literal backtick")
    if not text:
        return ""
    encoded = text.replace('"', "`")
    # Each statement is the text wrapped in quotes plus the printing dot.
    chunks = _literal_chunks(encoded, width, len('"".'))
    return "\n".join(f'"{chunk}".' for chunk in chunks)


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
