"""Boolean-function generator for Jaune."""

from collections.abc import Callable

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
    stored_inputs,
)


def jaune(truth_table: str) -> str:
    """Build a Jaune program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  All
    bits are read up front (``v``, ``ord-48``), then ``?`` jumps route the
    tree; each leaf prints with ``^`` and terminates.  Only inputs the tree
    branches on get a cell (``>`` after the read), so the tree navigates a
    span as wide as the real dependencies, and a leaf prints from its
    parent's test cell for one ``+``/``-``, and a node whose halves are
    ``0`` and ``1`` prints its own cell unbranched (``1`` and ``0``, after
    :func:`_inverted_inputs` reads it inverted).  Reading up front keeps the
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
    # A signed literal now includes ``-1?``; keep the decrement separate
    # from the label jump with an ignored character.
    out.append("1:2!#>>%&-x1?1!2:>^.")
    return "".join(out)


def _inverted_inputs(
    truth_table: str, perm: tuple[int, ...], constant: Callable[[int, int], bool]
) -> frozenset[int]:
    """Return the inputs with more ``10`` nodes than ``01`` nodes.

    ``+v-`` reads such an input as ``1 - x``, two characters (three after
    a clobbered read, which ``%`` clears) that turn each ``10`` node into a
    bare print and each ``01`` into the inverted one.
    """
    score = dict.fromkeys(perm, 0)
    for level, test in enumerate(perm):
        width = len(truth_table) >> level
        for lo in range(0, len(truth_table), width):
            mid = lo + width // 2
            if constant(lo, mid) and constant(mid, lo + width):
                score[test] += int(truth_table[lo]) - int(truth_table[mid])
    return frozenset(i for i in perm if score[i] > 0)


def _jaune_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Jaune program; see :func:`jaune`.

    Untested inputs are read into the cell the next read overwrites; a leaf
    prints from the cell it stands on (1 on then, 0 on else); the pointer's
    position on entry to a node is a function of level alone.  An inverted
    input swaps which half is ``then``.
    """
    n = _validate_truth_table(truth_table)
    label = [1]
    constant = constant_span_test(truth_table)
    flip = _inverted_inputs(truth_table, perm, constant)

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
    clobbered = False
    for i in range(n):
        if i in stored and i in flip:
            reads += "%+v-" if clobbered else "+v-"
        else:
            reads += "v"
        clobbered = i not in stored
        if i in stored:
            cell_of[i] = slot
            slot += 1
            reads += ">"
    # A clobbered read leaves its value under the pointer, so the cell the
    # reads finish on is blank only when the last read advanced off it.  A
    # whole-table constant prints from there and needs it zero, so step once
    # more when the final read clobbered -- and the entry cell moves with it.
    # Any other table prints only from test cells and walks straight back to
    # its first, so the last read's step off its cell is dropped instead.
    scratch = slot
    if not constant(0, 1 << n):
        if reads.endswith(">"):
            reads = reads[:-1]
            scratch = slot - 1
    elif n and (n - 1) not in stored:
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
        mid = (lo + hi) // 2
        (elo, ehi), (tlo, thi) = (lo, mid), (mid, hi)
        if perm[level] in flip:
            (elo, ehi), (tlo, thi) = (tlo, thi), (elo, ehi)
        # Halves 0 and 1 by cell value print the cell; 1 and 0 its inverse,
        # where a 1 jumps to one ``-`` and a 0 adds two before it.
        if (
            constant(lo, mid)
            and constant(mid, hi)
            and truth_table[lo] != truth_table[mid]
        ):
            if truth_table[tlo] == "1":
                return move(entry, cell) + "^."
            skip = fresh()
            return move(entry, cell) + f"{skip}?++{skip}:-^."
        then_lbl = fresh()
        then = node(level + 1, tlo, thi, cell, 1)
        else_ = node(level + 1, elo, ehi, cell, 0)
        return move(entry, cell) + f"{then_lbl}?{else_}{then_lbl}:{then}"

    return reads + node(0, 0, 2**n, scratch, None)
