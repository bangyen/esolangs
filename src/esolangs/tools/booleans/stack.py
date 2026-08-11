"""Boolean-function generators for stack-based languages."""


def _forth_const(value: int) -> str:
    """Forþ code pushing ``value`` (base-15 digits built with Horner's rule)."""
    digits = "0123456789ABCDEF"
    if value == 0:
        return "0"
    ds: list[int] = []
    v = value
    while v:
        ds.append(v % 15)
        v //= 15
    ds.reverse()
    prog = digits[ds[0]]
    for d in ds[1:]:
        prog += "F*" + digits[d] + "+"
    return prog


def _forth_combo(m: int) -> int:
    """Combo index of the leaf at heap position ``m`` (odd = left child)."""
    path = []
    while m > 0:
        path.append(0 if m % 2 else 1)
        m = (m - 1) // 2
    path.reverse()
    return sum(b << i for i, b in enumerate(path))


def forth(truth_table: str, n: int) -> str:
    """Build a Forþ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.  The
    program prints ``'0'`` or ``'1'``.

    Forþ reads a line with ``,`` and has no clean pop, so the generator
    builds a decision tree out of functions:     ``{ scope }`` stores a scope in
    the function table, and an internal node dispatches with ``base + ;``,
    which pops the top bit and calls ``table[base + bit]``.  Each input is
    read and normalized to 0/1 with ``,68*-``, the root dispatches with
    ``1+;``, and a leaf pushes ``48 + result`` which the final ``.`` prints.
    The definition indices are left on the stack below the result; the
    ``{ }`` construct reads (but does not pop) the top index, and ``;`` pops
    it, so the stale indices never get in the way of the dispatch arithmetic.
    """
    prog = []
    for m in range(1, 2 ** (n + 1) - 1):
        if m <= 2**n - 2:  # internal node: dispatch on the top bit
            body = _forth_const(2 * m + 1) + "+;"
        else:  # leaf: push the result byte
            result = int(truth_table[_forth_combo(m)])
            body = _forth_const(48 + result)
        prog.append(_forth_const(m) + "{" + body + "}")
    prog.append(",68*-" * n)  # read and normalize each input
    prog.append("1+;.")  # root dispatch, then print the result
    return "".join(prog)


def modulous(truth_table: str, n: int) -> str:
    """Build a Modulous program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), and ``n`` is the number of inputs.

    Modulous reads the inputs onto the stack with ``[INP INT]`` (top is the
    last input), then a decision tree branches on the top with
    ``[JMP F n IF 0/1]``, popping each checked bit. Each leaf pushes the
    result with ``[PSH INT]`` and prints it.
    """

    def build(rows: list[int], k: int) -> str:
        if len(rows) == 1:
            return f"[PSH INT {truth_table[rows[0]]}][PRT INT][END]"
        g0 = [r for r in rows if ((r >> (n - k)) & 1) == 0]
        g1 = [r for r in rows if ((r >> (n - k)) & 1) == 1]
        sub0 = build(g0, k - 1)
        sub1 = build(g1, k - 1)
        d = 2 + sub0.count("[")
        return f"[JMP F 2 IF 0][JMP F {d} IF 1][POP]{sub0}[POP]{sub1}"

    return "[INP INT]" * n + build(list(range(2**n)), n)


def _bfstack_encoder(n: int) -> str:
    """BFStack code turning the n inputs into the number ``1 + sum(bit*2^k)``.

    Each input is read with ``,`` and normalized to 0/1 with 48 ``-``s; if it
    is one, ``[<+w>]`` adds its weight ``w`` to the accumulator below it.
    The ``+1`` offset keeps the result nonzero so the decoder's outer ``[``
    always runs (a ``0`` result would be ambiguous with a skipped loop).
    """
    prog = ">>+"  # result cell (0) below the accumulator (1)
    for k in range(n):
        weight = 2 ** (n - 1 - k)
        prog += "," + "-" * 48 + "[" + "<" + "+" * weight + ">" + "]" + "<"
    return prog


def _bfstack_decoder(truth_table: str) -> str:
    """BFStack code mapping the encoded number to the table's result.

    The output is 1 for every input except the rows where the table is 0.
    Each such row maps to a distinct value of the ``+1``-offset number, so the
    decoder tests them by cumulative subtraction: ``[`` opens a ``while`` that
    only reaches the inner ``[<+>]`` (setting the result to 1) when the number
    survives every subtraction; hitting a zero row's value subtracts to 0 and
    skips the ``[<+>]`` instead, leaving the result 0.
    """
    zeros = [k + 1 for k, ch in enumerate(truth_table) if ch == "0"]
    if not zeros:
        return "[<+>]"  # always 1
    prog = "["
    prev = 0
    for z in zeros:
        prog += "-" * (z - prev) + "["
        prev = z
    prog += "[<+>]"
    prog += "]" * (len(zeros) + 1)
    return prog


def bfstack(truth_table: str, n: int) -> str:
    """Build a BFStack program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    BFStack is a pure stack machine, so the generator avoids branching
    entirely: it encodes the n inputs as the number ``1 + sum(bit*2^k)``
    (each ``,`` reads and normalizes a bit, ``[<+w>]`` adds its weight), then
    decodes it with nested ``[`` loops that only set the result to 1 when the
    number is not one of the table's zero rows.
    """
    return _bfstack_encoder(n) + _bfstack_decoder(truth_table) + "<" + "+" * 48 + "."


def unsquare(truth_table: str, n: int) -> str:
    """Build an Unsquare program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    Unsquare's ``>``/``<`` loop runs while the accumulator is neither 0 nor 1,
    so a 0/1 bit is turned into a loop condition by ``x`` (0 stays 0, 1
    becomes 2) and its negation by a stack-clean flip ``x->IA<`` (``0`` swaps
    to 1, ``1`` to 0).  Each input is read and reduced to 0/1 by ``>-<``
    (subtracting 2 until parity) and pushed; the decision tree then pops bits
    from the stack top (the last input first) and branches.  A branch that
    runs ends with ``IA`` (leaving acc = 1 so the sibling's ``FLIP x > <``
    guard skips), and each leaf pushes ``48 + entry`` and leaves acc = 0, so
    the final ``o`` prints exactly the matching row's entry.
    """
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")

    flip = "x->IA<"

    def leaf(row: int) -> str:
        value = 48 + int(truth_table[row])
        return ("IA" if value == 49 else "OA") + "+" * 24 + "P" + "OA"

    def build(rows: list[int], k: int) -> str:
        if len(rows) == 1:
            return leaf(rows[0])
        g1 = [row for row in rows if ((row >> k) & 1) == 1]
        g0 = [row for row in rows if ((row >> k) & 1) == 0]
        return f"Ax>{build(g1, k + 1)}IA<{flip}x>{build(g0, k + 1)}OA<"

    return "iA>-<P" * n + build(list(range(2**n)), 0) + "o"
