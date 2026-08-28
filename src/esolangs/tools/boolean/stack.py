"""Boolean-function generators for stack-based languages."""

from esolangs.tools.boolean.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    minterm_literals,
)


def _grapheme_push0() -> str:
    """Grapheme code pushing the integer 0 (``Z`` is intmode's zero digit)."""
    return "FZF"


def _grapheme_push1() -> str:
    """Grapheme code pushing the integer 1 (``10 / 10``)."""
    return "FAF" + "FAF" + "R"


def _grapheme_push65() -> str:
    """Grapheme code pushing 65 (``ord('A')``, the input normalization constant)."""
    return "FGF" + "FEF" + "FAF" + "R" + "B"  # 70 - (50 / 10)


def _grapheme_push_key(key: int) -> str:
    """Grapheme code pushing the integer variable key ``key`` (a multiple of 10)."""
    return "F" + chr(key // 10 + 64) + "F"


def grapheme(truth_table: str) -> str:
    """Build a Grapheme program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Grapheme reads a whole line with ``W`` and every non-empty string is
    truthy, so the generator uses a two-character input alphabet instead of
    ``'0'``/``'1'``: the harness feeds ``A`` for a one bit and ``%`` for a
    zero.  Each bit is normalized to the integer 0/1 with ``W 65 B T``
    (``B`` computes ``ord(bit) - 65``, which is 0 exactly for ``A``, and
    ``T`` maps zero to 1 and nonzero to 0), stored in a variable, and the
    table is evaluated as a sum of minterms: the result is ``1`` minus the
    sum of the ``0``-rows' minterms, or the sum of the ``1``-rows' minterms,
    whichever has fewer rows (each minterm is the arithmetic AND, ``S``, of
    the bits or their complements ``1 - b``).  Since exactly one row's
    minterm is 1 for any input, the accumulator holds the table entry, which
    ``Y`` prints.  No control-flow jumps are needed — only ``A``/``B``/``S``
    arithmetic and ``T``.
    """
    n = _validate_truth_table(truth_table)

    prog = [_grapheme_push65() + _grapheme_push_key(90) + "C"]  # vars[90] = 65
    for i in range(n):
        # W reads the bit; normalize to 0/1; store under key 10*(i+1).
        prog.append(
            "W"
            + _grapheme_push_key(90)
            + "D"
            + "B"
            + "T"
            + _grapheme_push_key(10 * (i + 1))
            + "C"
        )

    # Evaluate over the sparser side to bound the program size.
    zeros = [r for r in range(2**n) if truth_table[r] == "0"]
    ones = [r for r in range(2**n) if truth_table[r] == "1"]
    if len(zeros) <= len(ones):
        rows, acc, op = zeros, _grapheme_push1(), "B"  # acc = 1 - sum(0-row minterms)
    else:
        rows, acc, op = ones, _grapheme_push0(), "A"  # acc = sum(1-row minterms)
    prog.append(acc)
    for row in rows:
        prog.append(_grapheme_push1())  # start this minterm at 1
        for i, negated in minterm_literals(row, n):
            if negated:
                # factor = 1 - b_i
                prog.append(
                    _grapheme_push1() + _grapheme_push_key(10 * (i + 1)) + "D" + "B"
                )
            else:
                prog.append(_grapheme_push_key(10 * (i + 1)) + "D")  # factor = b_i
            prog.append("S")
        prog.append(op)  # fold the minterm into the accumulator
    prog.append("Y")
    return "".join(prog)


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


def forth(truth_table: str) -> str:
    """Build a Forþ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
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

    A subtree whose rows all agree answers in place -- the node pushes the
    result byte instead of dispatching, and its whole subtree goes
    unemitted.  That costs nothing to arrange because Forþ keys its scope
    table by the number pushed before ``{`` and looks it up with a default,
    so a gap in the numbering is simply a scope that never exists; no index
    has to move.  The rows a node stands for are a *stride* rather than a
    contiguous run (``_forth_combo`` reads the path least-significant bit
    first), so ``01010101`` collapses to the two root children while
    ``00001111`` is constant over an axis this tree never splits on and
    keeps every node.  The reads sit outside the tree, so a folded program
    consumes its input exactly as an unfolded one does.
    """
    n = _validate_truth_table(truth_table)
    last_internal = 2**n - 2

    def rows_under(m: int) -> list[int]:
        """Return the table rows the subtree rooted at heap index ``m`` covers.

        A leaf stands for the one row :func:`_forth_combo` names; an
        internal node stands for its two children's rows together.  Those
        rows are a *stride* rather than a contiguous run, because
        ``_forth_combo`` reads the path least-significant bit first -- so a
        table like ``11110000`` is constant over an axis this tree never
        splits on and folds nothing, while ``10101010`` folds hard.
        """
        if m > last_internal:
            return [_forth_combo(m)]
        return rows_under(2 * m + 1) + rows_under(2 * m + 2)

    prog = []
    folded: set[int] = set()
    for m in range(1, 2 ** (n + 1) - 1):
        if m in folded:
            # An ancestor already answered for this subtree, so its scope is
            # never called.  Forþ stores scopes in a dict keyed by the
            # pushed number and looks them up with a default, so a gap in
            # the numbering costs nothing -- the node simply never exists.
            continue
        if m <= last_internal:
            rows = rows_under(m)
            if len({truth_table[row] for row in rows}) == 1:
                # Every row under this node agrees, so the bits it would
                # branch on cannot change the answer: answer here and drop
                # the whole subtree.  The inputs are read up front, outside
                # the tree, so a folded program still consumes its input
                # exactly as an unfolded one does.
                body = _forth_const(_ASCII_ZERO + int(truth_table[rows[0]]))
                # Drop the *whole* subtree, not just the two children: a
                # grandchild is just as unreachable, and marking one level
                # leaves the deeper nodes emitted but never called.
                below = [2 * m + 1, 2 * m + 2]
                while below:
                    child = below.pop()
                    folded.add(child)
                    if child <= last_internal:
                        below += [2 * child + 1, 2 * child + 2]
            else:  # internal node: dispatch on the top bit
                body = _forth_const(2 * m + 1) + "+;"
        else:  # leaf: push the result byte
            result = int(truth_table[_forth_combo(m)])
            body = _forth_const(_ASCII_ZERO + result)
        prog.append(_forth_const(m) + "{" + body + "}")
    prog.append(",68*-" * n)  # read and normalize each input
    prog.append("1+;.")  # root dispatch, then print the result
    return "".join(prog)


def modulous(truth_table: str) -> str:
    """Build a Modulous program computing the given truth table.

    ``truth_table`` is a binary string of length 2**n indexed by the inputs
    (most significant first), ``n`` is the input count implied by the table length.

    Modulous reads the inputs onto the stack with ``[INP INT]`` (top is the
    last input), then a decision tree branches on the top with
    ``[JMP F n IF 0/1]``, popping each checked bit. Each leaf pushes the
    result with ``[PSH INT]`` and prints it.
    """
    n = _validate_truth_table(truth_table)

    def build(rows: list[int], k: int) -> str:
        if len({truth_table[row] for row in rows}) == 1:
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
        prog += "," + "-" * _ASCII_ZERO + "[" + "<" + "+" * weight + ">" + "]" + "<"
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


def bfstack(truth_table: str) -> str:
    """Build a BFStack program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BFStack is a pure stack machine, so the generator avoids branching
    entirely: it encodes the n inputs as the number ``1 + sum(bit*2^k)``
    (each ``,`` reads and normalizes a bit, ``[<+w>]`` adds its weight), then
    decodes it with nested ``[`` loops that only set the result to 1 when the
    number is not one of the table's zero rows.
    """
    n = _validate_truth_table(truth_table)
    return (
        _bfstack_encoder(n)
        + _bfstack_decoder(truth_table)
        + "<"
        + "+" * _ASCII_ZERO
        + "."
    )


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

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
    n = _validate_truth_table(truth_table)

    flip = "x->IA<"

    def leaf(row: int) -> str:
        value = _ASCII_ZERO + int(truth_table[row])
        return ("IA" if value == _ASCII_ONE else "OA") + "+" * 24 + "P" + "OA"

    def build(rows: list[int], k: int) -> str:
        if len({truth_table[row] for row in rows}) == 1:
            return leaf(rows[0])
        g1 = [row for row in rows if ((row >> k) & 1) == 1]
        g0 = [row for row in rows if ((row >> k) & 1) == 0]
        return f"Ax>{build(g1, k + 1)}IA<{flip}x>{build(g0, k + 1)}OA<"

    return "iA>-<P" * n + build(list(range(2**n)), 0) + "o"
