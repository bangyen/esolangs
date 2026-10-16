"""Defer repeated byte-tape residuals through unused level flags."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from itertools import pairwise

from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    move_text,
    subtree_ids,
)
from esolangs.generation.shared_block import ContinuationCost as _Cost
from esolangs.generation.shared_block import repeated_block, repeated_blocks


@dataclass(frozen=True, slots=True)
class FlagDialect:
    """Native moves and glyphs for a zero-clearing flag tree."""

    move: Callable[[int, int], str]
    one: str
    zero: str
    opener: str
    closer: str
    decrement: str
    retest: bool = False


def _tape_dialect(*, flip: bool) -> FlagDialect:
    """Return the brainfuck spelling; a flipped tree clears with ``+``."""
    return FlagDialect(
        lambda here, there: move_text(here, there, ">", "<"),
        one="+",
        zero="+" if flip else "-",
        opener="[",
        closer="]",
        decrement="-",
        retest=flip,
    )


def shared_flag_tree(
    truth_table: str,
    perm: tuple[int, ...],
    start: int,
    result: int,
    *,
    binary_leaves: bool = False,
    command_budget: int | None = None,
) -> tuple[str, int] | None:
    """Return the shorter admitted body of the single and multiple forms.

    ``single`` defers the one repeated block, ``multiple`` every repeated
    block.  Brainfuck, 40 random tables: ``multiple`` over ``single`` alone
    saves 1.9% at n=8 but 25.9% on majority (n=8), so it stays; the three
    unused-flag banks added at most 1.65% at n=8 (majority 0%) and went.
    """
    shared = repeated_block(truth_table)
    if shared is None:
        return None
    body = partial(
        flag_tree_body, truth_table, perm, start, result, binary_leaves=binary_leaves
    )
    bodies = [body(shared=shared)]
    blocks = repeated_blocks(truth_table)
    if len(blocks) > 1:
        bodies.append(body(shared_blocks=blocks))
    admitted = [
        form for form in bodies if command_budget is None or form[1] <= command_budget
    ]
    return min(admitted, key=lambda form: len(form[0])) if admitted else None


def flag_tree_body(
    truth_table: str,
    perm: tuple[int, ...],
    start: int,
    result: int,
    *,
    shared: tuple[int, int] | None = None,
    shared_blocks: tuple[tuple[int, int], ...] = (),
    flag_levels: tuple[int, ...] = (),
    binary_leaves: bool = False,
    flip: bool = False,
    dialect: FlagDialect | None = None,
    fold_zero: bool | None = None,
) -> tuple[str, int]:
    """Return a flag tree ending at result, and its worst command count.

    Inputs at cells 2*perm[i] are bits and following flags are zero; binary
    leaves may reserve the final flag for result. Flip-only loop closers
    retest the opener; a native dialect supplies its own recheck rule.
    A bank assigns each block a distinct unused flag no shallower than the
    block: the shallower ancestor that owns a younger flag would rewrite it
    before dispatch. Blocks sit at non-decreasing depths, so a body only
    defers into a later stage, and dispatch clears each flag before its body
    reuses it. Other pending flags stay zero on that path.
    """
    n = _validate_truth_table(truth_table)
    spelling = dialect or _tape_dialect(flip=flip)
    clear, set_one, decrement = spelling.zero, spelling.one, spelling.decrement
    opener, closer, retest = spelling.opener, spelling.closer, int(spelling.retest)
    blocks = (shared,) if shared is not None else shared_blocks
    depths = [depth for depth, _ in blocks]
    if flag_levels and (
        len(flag_levels) != len(blocks)
        or any(left > right for left, right in pairwise(depths))
        or len(set(flag_levels)) != len(flag_levels)
        or any(level < depth for level, depth in zip(flag_levels, depths, strict=True))
        or any(level >= n for level in flag_levels)
        or any(2 * perm[level] + 1 == result for level in flag_levels)
    ):
        raise ValueError("a residual bank needs distinct unused descendant flags")
    increasing = bool(flag_levels) or all(
        left < right for left, right in pairwise(depths)
    )
    if not increasing or any(not 0 <= depth < n for depth in depths):
        raise ValueError("deferred levels must be distinct, increasing input levels")
    pending_levels = flag_levels or tuple(depths)
    fold_zero = bool(blocks) if fold_zero is None else fold_zero
    ids = subtree_ids(truth_table)
    selected = {
        (depth, ids[depth][row >> (n - depth)]): i
        for i, (depth, row) in enumerate(blocks)
    }
    if len(selected) != len(blocks):
        raise ValueError("deferred definitions must name distinct residuals")
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
        emit(spelling.move(pos, target))
        pos = target

    def constant(i: int, combo: int) -> str | None:
        """Shared value of the level-``i`` subtree at ``combo``, else None."""
        span = 1 << (n - i)
        return truth_table[combo] if is_constant(combo, combo + span) else None

    def branch(i: int, combo: int) -> _Cost[int]:
        """Emit one side of node ``i``: a folded leaf or the child subtree."""
        start = count
        value = constant(i + 1, combo)
        if value is None:
            return node(i + 1, combo)
        if value == "1":
            move(result)
            emit(set_one)
        # value == "0": the leaf emits nothing
        return _Cost(count - start)

    def node(i: int, combo: int) -> _Cost[int]:
        """Emit node ``i``: test bit ``i``, run one side, leave flag_i = 0."""
        start = count
        key = (i, ids[i][combo >> (n - i)])
        if key in selected:
            move(flag(pending_levels[selected[key]]))
            emit(set_one)
            return _Cost(count - start, target=selected[key])
        bit_cell = bit(i)
        flg = flag(i)
        one = combo | (1 << (n - 1 - i))
        below = ids[i + 1]
        if below[combo >> (n - i - 1)] == below[one >> (n - i - 1)]:
            return branch(i, combo)  # halves agree: bit i cannot matter
        if binary_leaves and i == n - 1:
            if truth_table[combo] == "1":
                move(result)
                emit(set_one)
            move(bit_cell)
            emit(opener)
            skipped = count - start
            emit(clear)
            move(result)
            emit(set_one if truth_table[combo + 1] == "1" else decrement)
            move(bit_cell)
            emit(closer)
            return _Cost(max(skipped, count - start + retest))
        if fold_zero and constant(i + 1, combo) == "0":
            move(bit_cell)
            emit(opener)
            common = count - start
            emit(clear)
            body_start = count
            one_cost = branch(i, one)
            one_flat = count - body_start
            move(bit_cell)
            emit(closer)
            return _Cost(
                0,
                (_Cost(count - start - one_flat + retest, (one_cost,)), _Cost(common)),
            )
        move(flg)
        emit(set_one)  # flag_i = 1 (it is 0 by invariant)
        move(bit_cell)
        emit(opener)
        one_start = count
        emit(clear)  # clear the tested one-bit
        move(flg)
        emit(clear)  # clear the flag after selecting the one-side
        body_start = count
        one_cost = branch(i, one)
        one_flat = count - body_start
        move(bit_cell)
        emit(closer)  # bit is 0 now, so this exits
        one_cost = _Cost(count - one_start - one_flat + retest, (one_cost,))
        between = count
        move(flg)
        emit(opener)
        common = one_start - start + count - between
        zero_start = count
        emit(clear)  # clear the selected zero-side flag
        body_start = count
        zero_cost = branch(i, combo)
        zero_flat = count - body_start
        move(flg)
        emit(closer)
        zero_cost = _Cost(count - zero_start - zero_flat + retest, (zero_cost,))
        return _Cost(common, (one_cost, zero_cost))

    tree_cost = node(0, 0)
    stages = []
    for i, (depth, row) in enumerate(blocks):
        tail_start = count
        pending = flag(pending_levels[i])
        move(pending)
        dispatch_test = count - tail_start + 1
        emit(opener + clear)
        body_start = count
        del selected[depth, ids[depth][row >> (n - depth)]]
        body_cost = node(depth, row)
        body_flat = count - body_start
        move(pending)
        emit(closer)
        active = count - tail_start - body_flat + retest
        stages.append((i, body_cost, active, dispatch_test))

    tail_start = count
    move(result)
    tails: dict[int | None, int] = {None: count - tail_start}
    # Each emitted branch is evaluated once; deeper dispatch continuations
    # have already been priced when its definition is reached in reverse.
    for i, body_cost, active, skipped in reversed(stages):
        cost = active + body_cost.evaluate(tails)
        tails = {target: value + skipped for target, value in tails.items()}
        tails[i] = cost
    return "".join(parts), tree_cost.evaluate(tails)
