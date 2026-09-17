"""Boolean-function generators for Jaune and its multiply dialect."""

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
    stored_inputs,
)

# ROTfuck rotates the program after every command, so a firing bracket
# seeks its partner in the *rotated* program.  The escape, verified against
# the interpreter: each ``[`` body is a straight-line ``+-><`` block and
# the closing ``]`` a phantom at a position ``q`` with ``len(body) + 1 ≡ 0
# (mod 8)``.  Skip path: ``[`` fires, seeks ``]`` at depth 1, lands at
# ``q + 1`` in state ``p + 1``.  Body path: the body runs (pointer ends on
# the tested, still-nonzero cell); at ``q`` the phantom reads
# ``rot^len(body)(']') = '['`` which does not fire, advancing to ``q + 1``
# in state ``q + 1 ≡ p + 1``.  Both paths re-converge, so the rest encodes
# position-wise; a body command at offset ``j`` must have ``rot^{-j}(cmd)``
# non-bracket so the seek sees no bracket.  The generator is a branch-free
# minterm sum: bits ``b_i`` (cell ``i``) and complements ``c_i`` (cell
# ``n + i``) guard blocks counting mismatches into ``mc_k``; a block per
# minterm zeroes ``m_k`` iff ``mc_k != 0``; 1-row blocks accumulate the
# result, printed as ``48 + r``.


def jaune(truth_table: str) -> str:
    """Build a Jaune program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  All
    bits are read up front (``v``, ``ord-48``), then ``?`` jumps route the
    tree; each leaf prints with ``^`` and terminates.  Only inputs the tree
    branches on get a cell (``>`` after the read), so the tree navigates a
    span as wide as the real dependencies, and a leaf prints from its
    parent's test cell for one ``+``/``-``.  Reading up front keeps the
    input count constant: reads at the nodes let a folded tree skip them,
    and Jaune escaped the contract test only by not being in
    ``BY_FUNCTION``.  The split order is whichever is shortest
    (:func:`~esolangs.tools.helpers.best_input_order`); navigation costs one
    move per cell, measured not assumed.
    """
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _jaune_ordered)
    return _jaune_linear(truth_table)


def _jaune_linear(truth_table: str) -> str:
    """Emit a linear spatial table and travelling counter for Jaune."""
    n = _validate_truth_table(truth_table)
    out = ["v>" * n]

    # Cell n is counter 0; each row then owns one output cell and the next
    # counter cell.  Only one increment is needed for a true row.
    for bit in truth_table:
        out.append(">")
        if bit == "1":
            out.append("+")
        out.append(">")
    out.append("<" * (n + 2 * len(truth_table)))

    # Revisit each input, carry it in the hold cell, and add its unary weight
    # to counter 0.  The weights sum to T-1.
    for i in range(n):
        out.append("#")
        out.append(">" * (n - i))
        out.append("&" * (1 << (n - 1 - i)))
        if i + 1 < n:
            out.append("<" * (n - i - 1))

    # Move a decremented copy of the counter two cells at a time.  When it
    # reaches zero, the adjacent cell is the selected output.
    out.append("1:2!#>>%&-1?1!2:>^.")
    return "".join(out)


def _jaune_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Jaune program; see :func:`jaune`.

    Untested inputs are read into the cell the next read overwrites; a leaf
    prints from the cell it stands on (1 on then, 0 on else); the pointer's
    position on entry to a node is a function of level alone.
    """
    n = _validate_truth_table(truth_table)
    label = [1]
    constant = constant_span_test(truth_table)

    def fresh() -> int:
        label[0] += 1
        return label[0]

    def move(frm: int, to: int) -> str:
        return ">" * (to - frm) if to >= frm else "<" * (frm - to)

    stored = stored_inputs(truth_table, perm)
    # Reads run in input order; only a stored input advances the pointer, so
    # the kept bits occupy a contiguous block from cell 0.
    cell_of: dict[int, int] = {}
    reads = ""
    slot = 0
    for i in range(n):
        reads += "v"
        if i in stored:
            cell_of[i] = slot
            slot += 1
            reads += ">"
    # A clobbered read leaves its value under the pointer, so the cell the
    # reads finish on is blank only when the last read advanced off it.  A
    # whole-table constant prints from there and needs it zero, so step once
    # more when the final read clobbered -- and the entry cell moves with it.
    scratch = slot
    if n and (n - 1) not in stored:
        reads += ">"
        scratch = slot + 1

    def leaf(value: str, held: int | None) -> str:
        want = int(value)
        have = 0 if held is None else held
        adjust = "+" * (want - have) if want >= have else "-" * (have - want)
        return adjust + "^."

    def node(level: int, lo: int, hi: int, entry: int, held: int | None) -> str:
        if level == n or constant(lo, hi):
            return leaf(truth_table[lo], held)
        # A clobbered input has no cell to test.  Its bit cannot change the
        # answer, so the two halves of this span are value-identical and
        # descending into either one is the same function -- take the zero
        # half, which keeps the row span halving in step with the level.
        if perm[level] not in cell_of:
            return node(level + 1, lo, (lo + hi) // 2, entry, held)
        cell = cell_of[perm[level]]
        then_lbl = fresh()
        mid = (lo + hi) // 2
        then = node(level + 1, mid, hi, cell, 1)
        else_ = node(level + 1, lo, mid, cell, 0)
        return move(entry, cell) + f"{then_lbl}?{else_}{then_lbl}:{then}"

    return reads + node(0, 0, 2**n, scratch, None)


def jaune_multiply() -> str:
    """Build a Jaune program reading two decimal numbers and printing their product.

    Digits MSB first, one per line, up to ``*`` for the first operand and
    ``#`` for the second; prints the product with no leading zeros, at any
    length (no ``n``).  Jaune's cells do not wrap (JauneJS uses JS numbers),
    so an operand is one cell and ``^`` prints it.  A read loop runs on an
    always-one cell so ``?``/``!`` jump unconditionally; a digit is folded
    with ``v+``, ``#`` (copy to hold) and nine ``&`` (x10); a sentinel is
    detected by ``6+`` zeroing ``*`` (42).  Cells 0-4: first operand, digit
    scratch, second operand, result, trigger.
    """
    out: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        while pos < target:
            out.append(">")
            pos += 1
        while pos > target:
            out.append("<")
            pos -= 1

    def cmd(s: str) -> None:
        out.append(s)

    move(4)
    cmd("1+")  # cell 4 = 1: the unconditional loop-back trigger
    # read the first operand until '*': label 1 at cell 4
    cmd("1:")
    move(1)
    cmd("v")
    cmd("6+")  # '*' is 42, so ord-48 == -6; +6 zeroes it
    cmd("2!")  # a zero (the sentinel) exits to label 2
    cmd("6-")
    move(0)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(0)
    cmd("&")
    move(4)
    cmd("1?")  # always jump back to label 1
    cmd("2:")  # first operand done; the '*' was read at cell 1
    pos = 1
    move(4)
    # read the second operand until '#': label 4 at cell 4
    cmd("4:")
    move(1)
    cmd("v")
    cmd("13+")  # '#' is 35, so ord-48 == -13; +13 zeroes it
    cmd("3!")  # a zero (the sentinel) exits to label 3
    cmd("13-")
    move(2)
    cmd("#")
    cmd("&" * 9)
    move(1)
    cmd("#")
    move(2)
    cmd("&")
    move(4)
    cmd("4?")  # always jump back to label 4
    cmd("3:")  # second operand done; the '#' was read at cell 1
    pos = 1
    move(2)
    # multiply: while cell 2 != 0: cell 3 += cell 0; cell 2 -= 1
    cmd("5:")
    cmd("6!")
    move(0)
    cmd("#")
    move(3)
    cmd("&")
    move(2)
    cmd("1-")
    cmd("5?")
    cmd("6:")
    pos = 2
    move(3)
    cmd("^")
    cmd(".")
    return "".join(out)
