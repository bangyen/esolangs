r"""Boolean-function generator for 6:5."""

import string
from itertools import permutations

from esolangs.exceptions import GeneratorCapError
from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _ORDER_SEARCH_MAX,
    _greedy_input_order,
    _validate_truth_table,
    permute_truth_table,
    stored_inputs,
)

__all__ = ["six_five"]

# The 6-5 spec denotes operands.
# etc.)", so ``0..9A..Z`` names.
# This interpreter would decode.
# fallthrough, which is.
# (see the conformance note in.
# emit into that region.
_SIX_FIVE_MAX_LABEL = 10 + len(string.ascii_uppercase) - 1


def _six_five_label(value: int) -> str:
    r"""Return the single character 6-5 reads as ``value`` for a 7n/8n."""
    if not 0 <= value <= _SIX_FIVE_MAX_LABEL:
        raise ValueError(f"6-5 has no operand character for {value}")
    return str(value) if value < 10 else chr(value + 55)


def _six_five_markers(table: str) -> int:
    r"""How many branch labels the folded decision tree spends on ``table``."""
    if len(set(table)) == 1:
        return 0
    half = len(table) // 2
    return 1 + _six_five_markers(table[:half]) + _six_five_markers(table[half:])


def six_five(truth_table: str) -> str:
    r"""Build a 6-5 program computing the given truth table."""
    n = _validate_truth_table(truth_table)
    best = ""
    identity = tuple(range(n))
    # The same cap.
    # builds of an ``O(2**n)``.
    # generator renders past n == 6.
    # the cap is reachable here.
    # 17 seconds searching all.
    if n <= _ORDER_SEARCH_MAX:
        orders = list(permutations(range(n)))
    else:
        greedy = _greedy_input_order(truth_table, n)
        orders = [identity] if greedy == identity else [identity, greedy]
    for perm in orders:
        table = (
            truth_table if perm == identity else permute_truth_table(truth_table, perm)
        )
        candidate = _six_five_hoisted(table, perm)
        # An empty candidate means this.
        # so it is skipped rather than.
        if candidate and (not best or len(candidate) < len(best)):
            best = candidate
    if not best:
        # Every order overflowed the.
        # too many distinct subtrees.
        # spends labels per *input*.
        # fits at these widths.
        return _six_five_walk(truth_table)
    return best


def _six_five_walk(truth_table: str) -> str:
    r"""Emit the positional-walk 6-5 program: the whole table on the tape."""
    n = _validate_truth_table(truth_table)
    if n > _SIX_FIVE_MAX_LABEL:
        # Unreachable in practice: it.
        # is more characters than the.
        # the walk's arithmetic.
        # converted to the cap class.
        # half-applied.
        raise GeneratorCapError(  # pragma: no cover - needs a 2**36 table
            f"the 6-5 walk spends one branch label per input and there are "
            f"only 35, so n == {n} does not fit"
        )
    ones = [j for j, value in enumerate(truth_table) if value == "1"]
    out = ""
    if ones:
        # Rows past the last 1 stay.
        # tape, and a virgin cell.
        out += "1" * n
        for j in range(ones[-1] + 1):
            if truth_table[j] == "1":
                out += "62"
            if j != ones[-1]:
                out += "1"
        out += "3" * (2 * (n + ones[-1]))
    for i in range(n):
        out += "B" + "2" * 8 + "79" + "8" + _six_five_label(i + 1)
        out += "1" * 2 ** (n - 1 - i) + "4" + "1"
    return out + "6" * 8 + "A0"


def _six_five_dag_cost(truth_table: str) -> int:
    r"""Markers the shared build spends on ``truth_table``."""
    internal: set[str] = set()
    right_leaves: set[str] = set()

    def walk(window: str, *, right: bool) -> None:
        if len(set(window)) == 1:
            if right:
                right_leaves.add(window[0])
            return
        if window in internal:
            return
        internal.add(window)
        half = len(window) // 2
        walk(window[:half], right=False)
        walk(window[half:], right=True)

    walk(truth_table, right=False)
    return max(len(internal) - 1, 0) + len(right_leaves)


def _six_five_shared(
    truth_table: str,
    perm: tuple[int, ...],
    cell_of: dict[int, int],
    entry: int,
    n: int,
) -> str:
    r"""Emit the tree as a DAG, each distinct subtree laid down once."""
    # Distinct blocks, in the order.
    # subtree first, then the rest.
    # its index among the ``4``.
    # and both are decided here.
    order: list[str] = []
    seen: set[str] = set()

    def level_of(window: str) -> int:
        return n - (len(window).bit_length() - 1)

    def test_cell(window: str) -> tuple[str, int]:
        r"""Return the slice this block really tests, and the cell it uses."""
        level = level_of(window)
        while perm[level] not in cell_of:
            window = window[: len(window) // 2]
            level += 1
        return window, cell_of[perm[level]]

    def children(window: str) -> tuple[str, str]:
        tested, _ = test_cell(window)
        half = len(tested) // 2
        return tested[:half], tested[half:]

    def collect(window: str) -> None:
        if len(set(window)) == 1 or window in seen:
            return
        seen.add(window)
        order.append(window)
        for child in children(window):
            collect(child)

    collect(test_cell(truth_table)[0])
    right_leaf_values = sorted(
        {
            child[0]
            for parent in order
            for child in (children(parent)[1],)
            if len(set(child)) == 1
        }
    )
    # The root falls through rather.
    # marker; every other block is.
    # leaves follow them.
    label_of = {window: i for i, window in enumerate(order[1:], start=1)}
    leaf_label = {value: len(order) + i for i, value in enumerate(right_leaf_values)}

    def leaf_code(value: str, held: int) -> str:
        delta = _ASCII_ZERO + int(value) - held
        q, r = divmod(delta, 6)
        # one +5 beats five "62" pairs,.
        tail = "5" if r == 5 else "62" * r
        return "6" * q + tail + "A0"

    def right_branch(window: str) -> str:
        r"""Return the jump taken when the test succeeds."""
        if len(set(window)) == 1:
            return "8" + _six_five_label(leaf_label[window[0]])
        return "8" + _six_five_label(label_of[window])

    def block(window: str, arrive: int) -> str:
        r"""One node's code: test, jump right, then fall into the left arm."""
        _, cell = test_cell(window)
        left, right = children(window)
        code = _six_five_move(arrive, cell) + "78" + right_branch(right)
        if len(set(left)) == 1:
            return code + leaf_code(left[0], 8)
        # The left arm is a node of its.
        # test and then jumping --.
        # condition and has already.
        return code + "8" + _six_five_label(label_of[left])

    # Where the pointer sits on.
    # every other block from its.
    arrive_at = {order[0]: entry}
    for window in order:
        _, cell = test_cell(window)
        for child in children(window):
            if len(set(child)) != 1:
                arrive_at.setdefault(child, cell)
    out = block(order[0], arrive_at[order[0]])
    for window in order[1:]:
        out += "4" + block(window, arrive_at[window])
    for value in right_leaf_values:
        out += "4" + leaf_code(value, 9)
    return out


def _six_five_hoisted(truth_table: str, perm: tuple[int, ...]) -> str:
    r"""Emit the read-up-front 6-5 program for one input order."""
    n = _validate_truth_table(truth_table)
    # The tree is preferred while.
    # measurement was taken.
    # duplicates worth merging.
    # the order is given up on.
    shared = _six_five_markers(truth_table) > 35
    if shared and _six_five_dag_cost(truth_table) > 35:
        return ""
    if perm == tuple(range(n)) and not shared:
        return _six_five_stream_ordered(truth_table)
    stored = stored_inputs(truth_table, perm)
    # Reads run in input order;.
    # kept bits occupy a contiguous.
    # read reuses the one cell past.
    cell_of: dict[int, int] = {}
    reads = ""
    slot = 0
    pos = 0
    for i in range(n):
        reads += _six_five_move(pos, slot)
        pos = slot
        reads += "B"
        if i in stored:
            reads += "2" * 8
            cell_of[i] = slot
            slot += 1
    # A clobbered read leaves 48/49.
    # finish on is blank only when.
    # it.
    # its digit from zero, so it.
    # past the shared scratch when.
    scratch = slot + 1 if n and (n - 1) not in stored else slot
    marker = 0

    def leaf(value: str, entry: int, held: int | None) -> str:
        if held is None:
            # No node tested anything, so.
            digit = _ASCII_ZERO + int(value)
            return _six_five_move(entry, scratch) + _six_five_const(digit) + "A0"
        delta = _ASCII_ZERO + int(value) - held
        q, r = divmod(delta, 6)
        # one +5 beats five "62" pairs,.
        tail = "5" if r == 5 else "62" * r
        return "6" * q + tail + "A0"

    def node(level: int, lo: int, hi: int, entry: int, held: int | None) -> str:
        nonlocal marker
        if level == n or len(set(truth_table[lo:hi])) == 1:
            return leaf(truth_table[lo], entry, held)
        # A clobbered input has no cell.
        # answer, so the two halves of.
        # descending into either is the.
        # which keeps the row span.
        if perm[level] not in cell_of:
            return node(level + 1, lo, (lo + hi) // 2, entry, held)
        cell = cell_of[perm[level]]
        mid = (lo + hi) // 2
        nav = _six_five_move(entry, cell)
        # A label is the index of this.
        # the emitted string, so it is.
        # whose markers all precede it.
        sub0 = node(level + 1, lo, mid, cell, 8)
        marker += 1
        label = marker
        sub1 = node(level + 1, mid, hi, cell, 9)
        return nav + "78" + "8" + _six_five_label(label) + sub0 + "4" + sub1

    if shared:
        return reads + _six_five_shared(truth_table, perm, cell_of, pos, n)
    return reads + node(0, 0, 2**n, pos, None)


def _six_five_move(frm: int, to: int) -> str:
    r"""Pointer ops walking from cell ``frm`` to cell ``to``."""
    if to > frm:
        distance = to - frm
        return "1" * ((distance + 1) // 2) + ("3" if distance % 2 else "")
    return "3" * (frm - to)


def _six_five_stream_ordered(truth_table: str) -> str:
    r"""Emit the read-at-the-node 6-5 program; see :func:`six_five`."""
    n = _validate_truth_table(truth_table)
    labels = _six_five_markers(truth_table)
    if labels > 35:
        raise GeneratorCapError(
            "the 6-5 decision tree has 35 branch labels, but this table needs "
            f"{labels} after folding its constant subtrees (n == {n})"
        )
    marker = 0

    def build(rows: list[int], bit: int, base: int) -> str:
        nonlocal marker
        if len(rows) == 1:
            delta = _ASCII_ZERO + int(truth_table[rows[0]]) - base
            q, r = divmod(delta, 6)
            tail = "5" if r == 5 else "62" * r
            return "6" * q + tail + "A0"
        values = {truth_table[r] for r in rows}
        if len(values) == 1:
            # A constant subtree emits its.
            # branches that would all reach.
            # happen (a caller feeding.
            # would otherwise desync), but.
            # holding the last input.
            # per input -- and every cell.
            # constant, so no fixed suffix.
            # The leaf therefore steps to.
            # writes, and builds the digit.
            reads = "B" * (n - bit + 1)
            value = _ASCII_ZERO + int(values.pop())
            return reads + "13" + _six_five_const(value) + "A0"
        g0 = [r for r in rows if ((r >> (n - bit)) & 1) == 0]
        g1 = [r for r in rows if ((r >> (n - bit)) & 1) == 1]
        sub0 = build(g0, bit + 1, 8)
        label = marker + 1
        marker += 1
        sub1 = build(g1, bit + 1, 9)
        return "B" + "2" * 8 + "78" + "8" + _six_five_label(label) + sub0 + "4" + sub1

    return build(list(range(2**n)), 1, 0)


def _six_five_const(value: int) -> str:
    r"""Instructions adding ``value`` to the current cell."""
    q, r = divmod(value, 6)
    if r == 5:
        return "6" * q + "5"  # one +5 beats five +1 pairs.
    return "6" * q + "62" * r
