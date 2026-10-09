"""Defer one repeated byte-tape residual to its first unused level flag."""

from __future__ import annotations

from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    move_text,
    subtree_ids,
)
from esolangs.tools.shared_block import (
    BranchCost,
    add_cost,
    dispatch_cost,
    merge_cost,
    normal_cost,
    repeated_block,
)


def shared_flag_tree(
    truth_table: str,
    perm: tuple[int, ...],
    start: int,
    result: int,
    *,
    binary_leaves: bool = False,
) -> tuple[str, int] | None:
    """Return a byte-tape body ending at result, sharing one actual residual."""
    shared = repeated_block(truth_table)
    if shared is None:
        return None
    return flag_tree_body(
        truth_table, perm, start, result, shared=shared, binary_leaves=binary_leaves
    )


def flag_tree_body(
    truth_table: str,
    perm: tuple[int, ...],
    start: int,
    result: int,
    *,
    shared: tuple[int, int] | None = None,
    binary_leaves: bool = False,
    flip: bool = False,
) -> tuple[str, int]:
    """Return a flag tree ending at result, and its worst command count.

    Inputs at cells 2*perm[i] are bits and following flags are zero; binary
    leaves may reserve the final flag for result. Flip-only loop closers
    retest the opener; byte loops do not.
    """
    n = _validate_truth_table(truth_table)
    clear = "+" if flip else "-"
    retest = int(flip)
    fold_zero = shared is not None
    pending = 2 * perm[shared[0] if shared is not None else n - 1] + 1
    ids = subtree_ids(truth_table)
    is_constant = constant_span_test(truth_table)

    def bit(i: int) -> int:
        return 2 * perm[i]

    def flag(i: int) -> int:
        return 2 * perm[i] + 1

    parts: list[str] = []
    count = 0

    def emit(code: str) -> None:
        nonlocal count
        parts.append(code)
        count += len(code)

    pos = start

    def move(target: int) -> None:
        nonlocal pos
        emit(move_text(pos, target, ">", "<"))
        pos = target

    def constant(i: int, combo: int) -> str | None:
        """Shared value of the level-``i`` subtree at ``combo``, else None."""
        span = 1 << (n - i)
        return truth_table[combo] if is_constant(combo, combo + span) else None

    def branch(i: int, combo: int) -> BranchCost:
        """Emit one side of node ``i``: a folded leaf or the child subtree."""
        start = count
        value = constant(i + 1, combo)
        if value is None:
            return node(i + 1, combo)
        if value == "1":
            move(result)
            emit("+")
        # value == "0": the leaf emits nothing
        return count - start, None

    def node(i: int, combo: int) -> BranchCost:
        """Emit node ``i``: test bit ``i``, run one side, leave flag_i = 0."""
        start = count
        if (
            shared is not None
            and i == shared[0]
            and ids[i][combo >> (n - i)] == ids[i][shared[1] >> (n - i)]
        ):
            move(pending)
            emit("+")
            return None, count - start
        bit_cell = bit(i)
        flg = flag(i)
        one = combo | (1 << (n - 1 - i))
        below = ids[i + 1]
        if below[combo >> (n - i - 1)] == below[one >> (n - i - 1)]:
            return branch(i, combo)  # halves agree: bit i cannot matter
        if binary_leaves and i == n - 1:
            if truth_table[combo] == "1":
                move(result)
                emit("+")
            move(bit_cell)
            emit("[")
            skipped = count - start
            emit(clear)
            move(result)
            emit("+" if truth_table[combo + 1] == "1" else "-")
            move(bit_cell)
            emit("]")
            return max(skipped, count - start + retest), None
        if fold_zero and constant(i + 1, combo) == "0":
            move(bit_cell)
            emit("[")
            common = count - start
            emit(clear)
            body_start = count
            one_cost = branch(i, one)
            one_flat = count - body_start
            move(bit_cell)
            emit("]")
            return merge_cost(
                add_cost(one_cost, count - start - one_flat + retest),
                (common, None),
            )
        move(flg)
        emit("+")  # flag_i = 1 (it is 0 by invariant)
        move(bit_cell)
        emit("[")
        one_start = count
        emit(clear)  # clear the tested one-bit
        move(flg)
        emit(clear)  # clear the flag after selecting the one-side
        body_start = count
        one_cost = branch(i, one)
        one_flat = count - body_start
        move(bit_cell)
        emit("]")  # bit is 0 now, so this exits
        one_cost = add_cost(one_cost, count - one_start - one_flat + retest)
        between = count
        move(flg)
        emit("[")
        common = one_start - start + count - between
        zero_start = count
        emit(clear)  # clear the selected zero-side flag
        body_start = count
        zero_cost = branch(i, combo)
        zero_flat = count - body_start
        move(flg)
        emit("]")
        zero_cost = add_cost(zero_cost, count - zero_start - zero_flat + retest)
        return add_cost(merge_cost(one_cost, zero_cost), common)

    tree_cost = node(0, 0)
    tail_start = count
    if shared is not None:
        depth, row = shared
        move(pending)
        dispatch_test = count - tail_start + 1
        emit("[" + clear)
        body_start = count
        shared = None
        body_cost = node(depth, row)
        body_flat = count - body_start
        move(pending)
        emit("]")
        active = count - tail_start - body_flat + normal_cost(body_cost) + retest
        tree_cost = dispatch_cost(tree_cost, active, dispatch_test)
        tail_start = count

    move(result)
    return "".join(parts), normal_cost(tree_cost) + count - tail_start
