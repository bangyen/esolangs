"""6-5 Boolean program generator: a decision tree of ``7V`` tests.

:func:`six_five` routes a decision tree that folds constant subtrees,
jumps to its repeated subtrees where that is shorter, shares duplicates
past the label budget (35), falls back to a positional walk
(:func:`_six_five_walk`) when the distinct subtrees overflow, and past 35
inputs uses conditional strides (:func:`_six_five_guarded`), so it is total.

Size:
    O(T) worst case, small for structured tables; n=10 parity: 197 chars,
    n=10 and: 138 chars, n=10 random 1847: 5,292 chars.

Decisions:
    The positional walk spends exactly ``n`` labels.  Counting tree labels
    exactly rather than as a bound made one n == 6 table longer
    (:func:`_six_five_markers`).  Dropping the old DAG precheck shrinks
    sharing-heavy tables (:func:`_six_five_hoisted`).
"""

import string
from collections.abc import Callable
from typing import NamedTuple

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    input_weights,
    permute_truth_table,
    stored_inputs,
    subtree_ids,
    subtree_slot,
)
from esolangs.generation.wrap import _six_five
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

__all__ = ["six_five"]

# ``0..9A..Z`` names 0..35 per the spec; the interpreter's fallthrough
# past ``Z`` is undefined behaviour (``docs/limitations.md``), not a feature.
_SIX_FIVE_MAX_LABEL = 10 + len(string.ascii_uppercase) - 1


#: A walk read's -40, 48/49 to the 8/9 its ``79`` names, in the fewest
#: tokens: seven (``9`` is -6, ``2`` is -5), not eight ``2``s.
_SIX_FIVE_NORMALIZE = "9999922"

#: A tree read's 0 bit (1 is one more): under ``7n``'s cap of 35 by -17,
#: three tokens as is each leaf's +16..+18, where 8/9 took seven.
_SIX_FIVE_HELD = 31
_SIX_FIVE_TREE_NORMALIZE = "992"

#: The node test: skip the left arm's jump when the bit is 0.
_SIX_FIVE_TEST = "7V"


def _six_five_label(value: int) -> str:
    """Return the single character 6-5 reads as ``value`` for a 7n/8n operand."""
    if not 0 <= value <= _SIX_FIVE_MAX_LABEL:
        raise ValueError(f"6-5 has no operand character for {value}")
    return str(value) if value < 10 else chr(value + ord("A") - 10)


def _six_five_markers(table: str) -> int:
    """How many branch labels the folded decision tree spends on ``table``.

    One per internal node the fold leaves; a slice whose characters agree
    folds to a leaf.  Pass a permuted table for that order's count -- the
    35-label budget is a per-order gate.  Spans, not slices: O(2**n).  A
    node that copies or inverts its bit spends no label but still counts:
    the gate is a bound, so the tree-or-shared choice is unmoved (counted
    exactly, one n == 6 table took a tree 341 -> 561).
    """
    constant = constant_span_test(table)

    def count(lo: int, hi: int) -> int:
        if constant(lo, hi):
            return 0
        mid = (lo + hi) // 2
        return 1 + count(lo, mid) + count(mid, hi)

    return count(0, len(table))


def _six_five_halves(
    table: str, constant: Callable[[int, int], bool], lo: int, hi: int
) -> bool:
    """Whether the span is constant 0 then constant 1.

    Such a node copies the first bit: both arms print from the tested cell
    with one text (0 from 31, 1 from 32), so it needs no test and spends no
    label.
    """
    mid = (lo + hi) // 2
    return table[lo] + table[mid] == "01" and constant(lo, mid) and constant(mid, hi)


def six_five(truth_table: str) -> str:
    """Build a 6-5 program for ``truth_table`` (length ``2**n``, MSB first).

    Node and leaf shapes: ``_NodeEmitter.emit``, :func:`_six_five_leaf`.
    """
    # Identity and reverse: random n=7 10.8% (200 tables), parity/and/or 12-14%;
    # n >= 8 random exceeds the label budget either way, so 0%.
    best = _six_five_chosen(truth_table, _six_five_orders(truth_table))
    if not best:
        # Every order overflowed the budget even shared, so the table has
        # too many distinct subtrees for any tree-shaped emission.  The walk
        # spends labels per *input* rather than per subtree, so it always
        # fits at these widths.
        best = _six_five_walk(truth_table)
    # The last leaf ends the program, which halts at its end anyway.
    return best.removesuffix("0")


def _six_five_orders(truth_table: str) -> dict[tuple[int, ...], None]:
    """Return the two raced orders: identity and reverse."""
    n = _validate_truth_table(truth_table)
    identity = tuple(range(n))
    return dict.fromkeys((identity, tuple(reversed(identity))))


def _six_five_chosen(truth_table: str, orders: dict[tuple[int, ...], None]) -> str:
    """Return the shortest shared tree over ``orders``, or ``""`` if none fits.

    Each order's tree may jump to its repeated subtrees.
    """
    best = ""
    for perm in orders:
        table = (
            truth_table
            if perm == tuple(range(len(perm)))
            else permute_truth_table(truth_table, perm)
        )
        candidate = _six_five_hoisted(table, perm)
        # An empty candidate means this order overflowed the label budget,
        # so it is skipped rather than winning on length 0.
        if candidate and (not best or len(candidate) < len(best)):
            best = candidate
    return best


def _six_five_walk(truth_table: str) -> str:
    """Emit the positional-walk 6-5 program: the whole table on the tape.

    Spends exactly ``n`` labels: the branching moves the pointer, not the
    cursor.  Row ``j`` is preloaded at stride ``n + j`` (cell ``2 * (n + j)``;
    ``1`` moves two cells), ones as ``62``.  Each bit is read where the
    pointer stands: bit 1 skips the ``8n`` into ``2**(n-1-i)`` strides, bit 0
    jumps past them; both share one more stride, so after ``n`` bits the
    pointer is at the indexed row and the leaf adds 48 and prints.  The
    shared stride keeps every ``B`` behind the final cell.  Dense n == 10:
    10 labels, 5309 chars, 1024 rows in 12s.

    An ignored input is ``B1``, its shared stride alone, and the table is
    laid out at the rest.  It has no ``4``, so labels count essential inputs:
    ``8n`` names the n-th ``4``, and a skipped one misroutes every later jump.
    """
    n = _validate_truth_table(truth_table)
    if n > _SIX_FIVE_MAX_LABEL:
        return _six_five_guarded(truth_table)
    weights, projected = input_weights(truth_table, n)
    out = _six_five_preload(projected, n)
    label = 0
    for weight in weights:
        if not weight:
            out += "B1"
            continue
        label += 1
        out += "B" + _SIX_FIVE_NORMALIZE + "79" + "8" + _six_five_label(label)
        out += "1" * weight + "4" + "1"
    return out + "6" * 8 + "A0"


def _six_five_preload(truth_table: str, n: int) -> str:
    """Place table ones n strides from the entry cell; return there."""
    # Later zero rows stay virgin; the walk grows the tape on demand.
    last = truth_table.rfind("1")
    out = ["1" * n]
    for row in range(last + 1):
        if truth_table[row] == "1":
            out.append("62")
        if row != last:
            out.append("1")
    out.append("3" * (2 * (n + last)))
    return "".join(out)


def _six_five_guarded(truth_table: str) -> str:
    """Emit an O(T) positional walk with one label and no loops.

    Answers occupy odd cells; reads occupy the preceding even cells.
    Each bit normalizes to 31/32. Repeat ``7V 1`` for its weight: zero
    stays on its 31 and skips every move; one moves onto untouched zero
    cells, so every later test allows its move. A jump over the first
    bit's plain strides saves T-5 characters. The geometric weights give
    at most 13*T/2 + 4*n + 12 executed commands.
    """
    n = _validate_truth_table(truth_table)
    out = ["13" + _six_five_preload(truth_table, 0) + "3"]
    out.append("B" + _SIX_FIVE_TREE_NORMALIZE + "7W81")
    out.append("1" * (1 << (n - 1)) + "4")
    for bit in range(1, n):
        out.append("B" + _SIX_FIVE_TREE_NORMALIZE)
        out.append("7V1" * (1 << (n - 1 - bit)))
    out.append("13" + "6" * 8 + "A0")
    return "".join(out)


def _six_five_reads(
    n: int, stored: set[int], lazy: set[int]
) -> tuple[str, dict[int, int], int, int]:
    """Return the reads, each stored input's cell, the end pointer and next slot.

    Reads run in input order; only a stored input claims a cell, so the kept
    bits occupy a contiguous block from cell 0 and every clobbered read
    reuses the one cell past it.
    """
    cell_of: dict[int, int] = {}
    reads = ""
    slot = 0
    pos = 0
    for i in range(n):
        reads += _six_five_move(pos, slot)
        pos = slot
        reads += "B"
        if i in stored:
            reads += "" if i in lazy else _SIX_FIVE_TREE_NORMALIZE
            cell_of[i] = slot
            slot += 1
    return reads, cell_of, pos, slot


def _six_five_hoisted(
    truth_table: str,
    perm: tuple[int, ...],
) -> str:
    """Emit the read-up-front 6-5 program for one input order.

    ``truth_table`` is already permuted; ``perm`` names the stream input a
    node tests.  Returns ``""`` when this order overflows the 35 labels.
    Only inputs the tree branches on get a cell (others read into a shared
    scratch), so the kept bits are a contiguous block from cell 0.  A stored
    read is normalized by -17 where it lands, or at its one node (``7n`` is
    capped at 35, so 48/49 cannot be tested).  A leaf prints from the cell
    it stands on (32 on the jump, 31 on the fall-through); the pointer's entry
    position is a function of level alone.
    """
    n = _validate_truth_table(truth_table)
    # The tree is preferred while it fits: it is what every committed size
    # measurement was taken against, and sharing only pays once there are
    # duplicates worth merging.  Past the budget the DAG is tried before
    # the order is given up on.
    shared = _six_five_markers(truth_table) > _SIX_FIVE_MAX_LABEL
    stored = stored_inputs(truth_table, perm)
    constant = constant_span_test(truth_table)
    # An input the tree tests at one node alone is normalized there, not at
    # its read: the same three tokens, run only on the paths through it.
    uses = _six_five_use_counts(truth_table, perm, stored)
    lazy = set() if shared else {i for i, used in uses.items() if used == 1}
    reads, cell_of, pos, slot = _six_five_reads(n, stored, lazy)
    # A clobbered read leaves 48/49 under the pointer, so the cell the reads
    # finish on is blank only when the last read was stored and advanced past
    # it.  A whole-table constant has no parent cell to print from and builds
    # its digit from zero, so it needs a cell no read ever wrote: step one
    # past the shared scratch when the final read clobbered.
    scratch = slot + 1 if n and (n - 1) not in stored else slot
    ids = subtree_ids(truth_table)  # O(2**n), so a subtree's name is O(1)
    tree = _Tree(truth_table, perm, constant, cell_of, ids, lazy, scratch)

    def emit(layout: _Layout) -> str:
        return _NodeEmitter(layout, tree).emit(0, 0, 2 ** len(perm), pos, None)

    # One layout handles sharing both inside and beyond the plain-tree budget.
    # The old DAG precheck rejected layouts the emitter can fit: 50 seeded
    # dense n=7 tables shrink from 37,828 to 17,803 characters without it.
    plain = _Layout.shared(emit) if shared else emit(_Layout())
    if not plain:
        return ""
    jumped = _Layout.shared(emit) if not shared else ""
    return reads + (jumped if jumped and len(jumped) < len(plain) else plain)


class _Layout:
    """Lay out a 6-5 tree's branches, jumping to a repeated subtree's copy.

    ``8n`` names the n-th ``4`` in the program, not a scope, so a branch
    may name a subtree emitted for another parent.  A right subtree already
    has a ``4``; a left one falls through, so a left copy that is jumped to
    later gets a ``4`` of its own.  Which ones are is known only after the
    layout, so :meth:`shared` lays the tree out twice: a first pass records
    the copies jumped to, the second marks exactly those.  Plain
    (``share`` false) it is the unshared tree.
    """

    def __init__(
        self,
        *,
        share: bool = False,
        probe: bool = False,
        targets: frozenset[tuple[int, ...]] = frozenset(),
    ) -> None:
        self.share = share
        self.probe = probe
        self.targets = targets
        self.marker = 0
        self.placed: dict[tuple[int, ...], int] = {}
        self.jumped: set[tuple[int, ...]] = set()

    @classmethod
    def shared(cls, tree: Callable[["_Layout"], str]) -> str:
        """Lay ``tree`` out shared; ``""`` if it overflows the labels."""
        probe = cls(share=True, probe=True)
        tree(probe)
        final = cls(share=True, targets=frozenset(probe.jumped))
        text = tree(final)
        return text if final.marker <= _SIX_FIVE_MAX_LABEL else ""

    def agrees(self, ids: list[list[int]], level: int, lo: int) -> bool:
        """Whether a shared layout passes over this test: its halves agree."""
        if not self.share:
            return False
        block = lo >> (len(ids) - 1 - level)
        return ids[level + 1][2 * block] == ids[level + 1][2 * block + 1]

    def name(
        self,
        ids: list[list[int]],
        level: int,
        lo: int,
        entry: int,
        *,
        skip: bool,
        leaf: tuple[int, ...],
    ) -> tuple[int, ...] | None:
        """Name the subtree at rows ``lo..`` of ``level`` by what fixes its code.

        A node's code is fixed by its rows and ``entry``, a leaf's by its bit
        and ``leaf`` (the value it builds on, say).  ``skip`` follows the
        tests :meth:`agrees` passes over, when passing over one emits nothing.
        """
        if not self.share:
            return None
        block = lo >> (len(ids) - 1 - level)
        _level, _block, key = subtree_slot(ids, level, block, skip=skip)
        return (*key, *leaf) if key[0] < 0 else (*key, entry)

    def _label(self, value: int) -> str:
        # A probe may run past the budget; its text is thrown away.
        return _six_five_label(min(value, _SIX_FIVE_MAX_LABEL))

    def branch(
        self,
        zero: tuple[int, ...] | None,
        build_zero: Callable[[], str],
        one: tuple[int, ...] | None,
        build_one: Callable[[], str],
    ) -> str:
        """Return a node's test, its jump right, and both arms.

        A label is the index of its ``4`` among every ``4`` in the emitted
        string, so the right arm's is allocated *after* the left arm, whose
        markers all precede it.  An arm already emitted is a jump.
        """
        if zero in self.placed:
            self.jumped.add(zero)
            left = "8" + self._label(self.placed[zero])
        else:
            left = ""
            if zero is not None and (self.probe or zero in self.targets):
                self.marker += 1
                self.placed[zero] = self.marker
                left = "" if self.probe else "4"
            left += build_zero()
        if one in self.placed:
            self.jumped.add(one)
            return _SIX_FIVE_TEST + "8" + self._label(self.placed[one]) + left
        self.marker += 1
        label = self.marker
        if one is not None:
            self.placed[one] = label
        right = "4" + build_one()
        return _SIX_FIVE_TEST + "8" + self._label(label) + left + right


def _six_five_node_kind(
    truth_table: str,
    constant: Callable[[int, int], bool],
    perm: tuple[int, ...],
    cells: set[int] | dict[int, int],
    level: int,
    lo: int,
    hi: int,
) -> tuple[str, int]:
    """Classify the span at ``level`` over rows ``[lo, hi)``; return (kind, mid).

    ``leaf``: deep enough, or constant, so the span folds.  ``skip``: the
    level's input is not in ``cells``, so only the zero half is descended.
    ``copy``: the halves are constant 0 then 1, so the node prints its bit
    with no test.  ``branch``: a real test over both halves.  The emitter
    and the use counter share this one classification instead of each
    re-walking the same leaf/skip/copy/branch decisions by hand; ``cells``
    is the stored-input set for counting, the cell map for emitting.
    """
    mid = (lo + hi) // 2
    if level == len(perm) or constant(lo, hi):
        return "leaf", mid
    if perm[level] not in cells:
        return "skip", mid
    if _six_five_halves(truth_table, constant, lo, hi):
        return "copy", mid
    return "branch", mid


def _six_five_use_counts(
    truth_table: str, perm: tuple[int, ...], stored: set[int]
) -> dict[int, int]:
    """Count the tree paths that test each stored input, to find the lazy ones.

    Mirrors the walk ``_NodeEmitter.emit`` will descend, via the shared
    :func:`_six_five_node_kind`: a copy node (``"01"`` halves) reads its
    input once per subtree it copies, counted as two paths.  A stored
    input tested on exactly one path is normalized at that node rather
    than at its read.
    """
    constant = constant_span_test(truth_table)
    uses = dict.fromkeys(stored, 0)

    def tally(level: int, lo: int, hi: int) -> None:
        kind, mid = _six_five_node_kind(
            truth_table, constant, perm, stored, level, lo, hi
        )
        if kind == "leaf":
            return
        if kind == "skip":
            tally(level + 1, lo, mid)
            return
        if kind == "copy":
            uses[perm[level]] += 2
            return
        uses[perm[level]] += 1
        tally(level + 1, lo, mid)
        tally(level + 1, mid, hi)

    tally(0, 0, 2 ** len(perm))
    return uses


def _six_five_leaf(value: str, entry: int, held: int | None, scratch: int) -> str:
    """Emit the leaf printing ``value`` from the cell it is entered on.

    ``held`` is the value the entry cell is known to hold (``None`` when no
    node tested anything); the leaf adds the difference to it.  A held-less
    leaf builds its digit from zero on ``scratch``.
    """
    if held is None:
        # No node tested anything, so no cell holds a known value.
        digit = _ASCII_ZERO + int(value)
        return _six_five_move(entry, scratch) + _six_five_const(digit) + "A0"
    return _six_five_const(_ASCII_ZERO + int(value) - held) + "A0"


class _Tree(NamedTuple):
    """What every node of one order's hoisted tree reads."""

    truth_table: str
    perm: tuple[int, ...]
    constant: Callable[[int, int], bool]
    cell_of: dict[int, int]
    ids: list[list[int]]
    lazy: set[int]
    scratch: int


class _NodeEmitter:
    """Emit the nodes of one hoisted tree over one layout.

    Holds the two things every node needs -- the layout being laid out
    over and the tree being read -- so a node call carries only the span
    and the pointer state that actually change from node to node.
    """

    def __init__(self, layout: _Layout, tree: _Tree) -> None:
        self.layout = layout
        self.tree = tree

    def emit(self, level: int, lo: int, hi: int, entry: int, held: int | None) -> str:
        """Emit one node (or folded leaf) of the hoisted tree.

        A node is ``7V``: ``7`` compares the cell to 31, a zero bit skips
        the ``8n`` jump into the left subtree, a one bit jumps to the
        n-th ``4``.  ``entry`` is the cell the pointer stands on; ``held``
        the value known to be there.  A leaf prints from the cell it
        stands on (32 on the jump, 31 on the fall-through); the pointer's
        entry position is a function of level alone.
        """
        tree = self.tree
        kind, mid = _six_five_node_kind(
            tree.truth_table,
            tree.constant,
            tree.perm,
            tree.cell_of,
            level,
            lo,
            hi,
        )
        if kind == "leaf":
            return _six_five_leaf(tree.truth_table[lo], entry, held, tree.scratch)
        # A clobbered input has no cell to test.  Its bit cannot change the
        # answer, so the two halves of this span are value-identical and
        # descending into either is the same function -- take the zero half,
        # which keeps the row span halving in step with the level.  Shared,
        # any test whose halves agree is passed over the same way.
        if kind == "skip" or self.layout.agrees(tree.ids, level, lo):
            return self.emit(level + 1, lo, mid, entry, held)
        cell = tree.cell_of[tree.perm[level]]
        nav = _six_five_move(entry, cell)
        if kind == "copy":
            # A copy node's input counts two paths, so it is never lazy:
            # its read was normalized at the read, and the leaf prints
            # the held bit from 31/32.
            return nav + _six_five_leaf("0", cell, _SIX_FIVE_HELD, tree.scratch)
        return self._test_node(level, lo, mid, hi, cell, nav)

    def _test_node(
        self, level: int, lo: int, mid: int, hi: int, cell: int, nav: str
    ) -> str:
        """Emit a real ``7V`` branch node, both arms sharing by name."""
        tree = self.tree
        if tree.perm[level] in tree.lazy:
            nav += _SIX_FIVE_TREE_NORMALIZE

        def zero() -> str:
            return self.emit(level + 1, lo, mid, cell, _SIX_FIVE_HELD)

        def one() -> str:
            return self.emit(level + 1, mid, hi, cell, _SIX_FIVE_HELD + 1)

        # No inverted-bit print: from 31/32 it is 17 characters to a node's 14.
        # A child's code is fixed by its rows and the cell it is entered from,
        # the parent's, so that pair names it for sharing.
        layout = self.layout
        return nav + layout.branch(
            layout.name(tree.ids, level + 1, lo, cell, skip=True, leaf=(0,)),
            zero,
            layout.name(tree.ids, level + 1, mid, cell, skip=True, leaf=(1,)),
            one,
        )


def _six_five_move(frm: int, to: int) -> str:
    """Pointer ops walking from cell ``frm`` to cell ``to``.

    ``1`` steps two right, ``3`` one left (a no-op at cell 0), so rightward
    by ``d`` is ``ceil(d / 2)`` ones plus a ``3`` when ``d`` is odd.
    """
    if to > frm:
        distance = to - frm
        return "1" * ((distance + 1) // 2) + ("3" if distance % 2 else "")
    return "3" * (frm - to)


def _six_five_const(value: int) -> str:
    """Instructions adding nonnegative ``value`` to the current cell, fewest first.

    ``k = ceil(value / 6)`` tokens of ``6``/``5`` reach all of ``[5k, 6k]``,
    every leaf's 16..18 and 48..49 included; ``62`` pairs made +40 cost 14
    to +41's 7, so 0-leaves paid double.  Below 20, ``6``s then ``62`` pairs.
    """
    k = -(-value // 6)
    if 5 * k <= value:
        return "6" * (value - 5 * k) + "5" * (6 * k - value)
    q, r = divmod(value, 6)
    # A remainder of five already satisfies 5*k <= value.
    return "6" * q + "62" * r


LANGUAGE = Language(
    "6-5",
    "six_five",
    category="tape_based",
    boolean=six_five,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    # 7n/8n are two-character tokens; see ``_SIX_FIVE_COMMAND``.
    wrap=_six_five,
)
