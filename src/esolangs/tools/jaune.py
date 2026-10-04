"""Boolean-function generator for Jaune."""

from collections.abc import Callable

from esolangs._jaune import JauneDialect
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    in_input_order,
    stored_inputs,
    subtree_ids,
    subtree_slot,
)


def jaune(
    truth_table: str,
    *,
    cell_modulus: int | None = None,
    tape_size: int | None = None,
    boundary: str = "clamp",
    eof: str = "error",
    undefined_targets: str = "error",
) -> str:
    """Build a Jaune program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  All
    bits are read up front (``v``, integer tokens), then ``?`` jumps route the
    tree; each leaf prints with ``^`` and terminates.  Only inputs the tree
    branches on get a cell (``>`` after the read), so the tree navigates a
    span as wide as the real dependencies, and a leaf prints from its
    parent's test cell for one ``+``/``-``, and a node whose halves are
    ``0`` and ``1`` prints its own cell unbranched (``1`` and ``0``, after
    :func:`_inverted_inputs` reads it inverted).  Reading up front keeps the
    input count constant: reads at the nodes let a folded tree skip them,
    and Jaune escaped the contract test only by not being in
    ``BY_FUNCTION``. Splits stay in input order; navigation costs one
    move per cell, measured not assumed.

    A repeated subtree is laid out once and jumped to (``share`` in
    :func:`_jaune_ordered`). Sharing never grows a table through four inputs
    (exhaustively checked). The shared tree lays out
    distinct subtables alone in O(T).  Over the 256
    three-input tables that is 7,437 to 7,199 characters (3.2%); over 200
    seeded five-input tables, 47,973 to 19,568 (59.2%), where the unshared
    tree would give 29,291.
    """
    n = _validate_truth_table(truth_table)
    dialect = JauneDialect(cell_modulus, tape_size, boundary, eof, undefined_targets)
    stored = stored_inputs(truth_table, tuple(range(n)))
    required = len(stored) + int(n - 1 not in stored)
    if not stored:
        required = 2
    if dialect.tape_size is not None and dialect.tape_size < required:
        raise ValueError(f"Boolean generation requires at least {required} tape cells")
    return in_input_order(truth_table, _jaune_shared)


def _jaune_shared(truth_table: str, perm: tuple[int, ...]) -> str:
    """Return one order's program with its repeated subtrees jumped to."""
    return _jaune_ordered(truth_table, perm, share=True)


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


class _JauneLabels:
    """Track first copies and replay only the labels reached by shared jumps."""

    def __init__(self) -> None:
        self.next_label = 1
        self.placed: dict[tuple[int, ...], int] = {}
        self.jumped: set[tuple[int, ...]] = set()
        self.targets: set[tuple[int, ...]] = set()
        self.probe = False

    def fresh(self) -> int:
        self.next_label += 1
        return self.next_label

    def first(self, key: tuple[int, ...] | None, lbl: int | None = None) -> str:
        """Place a first copy; return the label it needs if jumped to later."""
        if key is None or not (self.probe or key in self.targets or lbl):
            return ""
        self.placed[key] = lbl or self.fresh()
        return "" if lbl or self.probe else f"{self.placed[key]}:"

    def render(self, build: Callable[[], str], *, share: bool) -> str:
        """Emit once, or probe shared targets before replaying with their labels."""
        self.probe = share
        if not share:
            return build()
        build()
        self.probe = False
        self.targets.update(self.jumped)
        self.next_label = 1
        self.placed.clear()
        return build()


def _jaune_ordered(
    truth_table: str, perm: tuple[int, ...], *, share: bool = False
) -> str:
    """Emit one input order's Jaune program; see :func:`jaune`.

    Untested inputs are read into the cell the next read overwrites; a leaf
    prints from the cell it stands on (1 on then, 0 on else); the pointer's
    position on entry to a node is a function of level alone.  An inverted
    input swaps which half is ``then``.

    With ``share`` a subtree equal to one already laid out jumps to it:
    ``X?`` for a then arm, ``Y!`` for an else arm, as the tested cell holds
    0 or 1.  A node's code is fixed by its rows and the cell it is entered
    from (its parent's), a leaf's by its value and the value it adjusts
    from, so those name a copy.  A test whose halves agree is passed over.
    A then arm's first copy has its label already; any other copy that is
    jumped to gets one, and which those are is known only after the layout,
    so the tree is laid out twice: a probe records them, the second pass
    labels exactly those.
    """
    n = _validate_truth_table(truth_table)
    labels = _JauneLabels()
    constant = constant_span_test(truth_table)
    flip = _inverted_inputs(truth_table, perm, constant)
    ids = subtree_ids(truth_table)  # O(2**n), so a subtree's name is O(1)

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

    def name(level: int, lo: int, entry: int, held: int) -> tuple[int, ...] | None:
        if not share:
            return None
        _level, _block, key = subtree_slot(ids, level, lo >> (n - level), skip=True)
        return (*key, held) if key[0] < 0 else (*key, entry)

    def arm(level: int, lo: int, hi: int, cell: int, held: int) -> tuple[str, int]:
        """Return an arm's code and, for a copy laid out before, its label."""
        key = name(level, lo, cell, held)
        if key in labels.placed:
            labels.jumped.add(key)
            return "", labels.placed[key]
        return labels.first(key) + node(level, lo, hi, cell, held), 0

    def node(level: int, lo: int, hi: int, entry: int, held: int | None) -> str:
        if level == n or constant(lo, hi):
            return leaf(truth_table[lo], held)
        # A clobbered input has no cell to test.  Its bit cannot change the
        # answer, so the two halves of this span are value-identical and
        # descending into either one is the same function -- take the zero
        # half, which keeps the row span halving in step with the level.
        # Shared, any test whose halves agree is passed over the same way.
        block = lo >> (n - level)
        agrees = share and ids[level + 1][2 * block] == ids[level + 1][2 * block + 1]
        if perm[level] not in cell_of or agrees:
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
            skip = labels.fresh()
            return move(entry, cell) + f"{skip}?++{skip}:-^."
        nav = move(entry, cell)
        then_key = name(level + 1, tlo, cell, 1)
        else_key = name(level + 1, elo, cell, 0)
        both = then_key not in labels.placed and else_key not in labels.placed
        if both and else_key in labels.targets and then_key not in labels.targets:
            # The else arm is labelled for its copies, so ``!`` jumps to it
            # and the then arm falls through: one label, not two.
            then = node(level + 1, tlo, thi, cell, 1)
            else_, else_at = arm(level + 1, elo, ehi, cell, 0)
            return nav + f"{else_at or labels.placed[else_key]}!{then}{else_}"
        if both:
            # Both arms laid out here: the then arm's label is the branch's.
            then_lbl = labels.fresh()
            labels.first(then_key, then_lbl)
            then = node(level + 1, tlo, thi, cell, 1)
            else_, else_at = arm(level + 1, elo, ehi, cell, 0)
            if else_at:
                # The then arm held a copy of the else arm, laid out first.
                return nav + f"{else_at}!{then_lbl}:{then}"
            return nav + f"{then_lbl}?{else_}{then_lbl}:{then}"
        then, then_at = arm(level + 1, tlo, thi, cell, 1)
        else_, else_at = arm(level + 1, elo, ehi, cell, 0)
        if then_at and else_at:
            return nav + f"{then_at}?{else_at}!"
        if then_at:
            return nav + f"{then_at}?{else_}"
        return nav + f"{else_at}!{then}"

    return labels.render(lambda: reads + node(0, 0, 2**n, scratch, None), share=share)
