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
    #: The result cell's write and its undo, when they differ from the
    #: flag's ``one`` and ``decrement`` (a result preset to 1, cleared by leaves).
    leaf: str = ""
    unleaf: str = ""


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
    blocks = (shared,) if shared is not None else shared_blocks
    pending_levels = _pending_levels(n, perm, result, blocks, flag_levels)
    tree = _FlagTree(
        truth_table,
        n,
        perm,
        result,
        blocks,
        pending_levels,
        dialect or _tape_dialect(flip=flip),
        binary_leaves=binary_leaves,
        fold_zero=bool(blocks) if fold_zero is None else fold_zero,
        pos=start,
    )
    return tree.emit_all()


def _pending_levels(
    n: int,
    perm: tuple[int, ...],
    result: int,
    blocks: tuple[tuple[int, int], ...],
    flag_levels: tuple[int, ...],
) -> tuple[int, ...]:
    """Return the level whose flag defers each block; refuse an unsound bank."""
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
    return flag_levels or tuple(depths)


class _FlagTree:
    """One flag tree's emitted text, head position and command count."""

    def __init__(
        self,
        truth_table: str,
        n: int,
        perm: tuple[int, ...],
        result: int,
        blocks: tuple[tuple[int, int], ...],
        pending_levels: tuple[int, ...],
        spelling: FlagDialect,
        *,
        binary_leaves: bool,
        fold_zero: bool,
        pos: int,
    ) -> None:
        self.table, self.n, self.perm, self.result = truth_table, n, perm, result
        self.blocks, self.pending_levels = blocks, pending_levels
        self.spelling, self.retest = spelling, int(spelling.retest)
        self.binary_leaves, self.fold_zero = binary_leaves, fold_zero
        self.pos = pos
        self.parts: list[str] = []
        self.count = 0
        self.ids = subtree_ids(truth_table)
        self.selected = {
            (depth, self.ids[depth][row >> (n - depth)]): i
            for i, (depth, row) in enumerate(blocks)
        }
        if len(self.selected) != len(blocks):
            raise ValueError("deferred definitions must name distinct residuals")
        self.is_constant = constant_span_test(truth_table)

    def flag(self, i: int) -> int:
        return 2 * self.perm[i] + 1

    def emit(self, code: str) -> None:
        self.parts.append(code)
        self.count += len(code)

    def move(self, target: int) -> None:
        self.emit(self.spelling.move(self.pos, target))
        self.pos = target

    def constant(self, i: int, combo: int) -> str | None:
        """Shared value of the level-``i`` subtree at ``combo``, else None."""
        span = 1 << (self.n - i)
        return self.table[combo] if self.is_constant(combo, combo + span) else None

    def branch(self, i: int, combo: int) -> _Cost[int]:
        """Emit one side of node ``i``: a folded leaf or the child subtree."""
        start = self.count
        value = self.constant(i + 1, combo)
        if value is None:
            return self.node(i + 1, combo)
        if value == "1":
            self.move(self.result)
            self.emit(self.spelling.leaf or self.spelling.one)
        # value == "0": the leaf emits nothing
        return _Cost(self.count - start)

    def guarded(self, cell: int, i: int, combo: int) -> tuple[int, _Cost[int], int]:
        """Emit ``[clear side]`` on ``cell``: its span, side cost and start."""
        self.move(cell)
        self.emit(self.spelling.opener)
        side_start = self.count
        self.emit(self.spelling.zero)
        body_start = self.count
        cost = self.branch(i, combo)
        flat = self.count - body_start
        self.move(cell)
        self.emit(self.spelling.closer)
        return self.count - side_start - flat + self.retest, cost, side_start

    def node(self, i: int, combo: int) -> _Cost[int]:
        """Emit node ``i``: test bit ``i``, run one side, leave flag_i = 0."""
        start = self.count
        key = (i, self.ids[i][combo >> (self.n - i)])
        if key in self.selected:
            self.move(self.flag(self.pending_levels[self.selected[key]]))
            self.emit(self.spelling.one)
            return _Cost(self.count - start, target=self.selected[key])
        one = combo | (1 << (self.n - 1 - i))
        below = self.ids[i + 1]
        if below[combo >> (self.n - i - 1)] == below[one >> (self.n - i - 1)]:
            return self.branch(i, combo)  # halves agree: bit i cannot matter
        if self.binary_leaves and i == self.n - 1:
            return self.binary_leaf(combo, start)
        if self.fold_zero and self.constant(i + 1, combo) == "0":
            span, one_cost, one_start = self.guarded(2 * self.perm[i], i, one)
            common = one_start - start
            return _Cost(0, (_Cost(common + span, (one_cost,)), _Cost(common)))
        return self.two_sided(i, combo, one, start)

    def binary_leaf(self, combo: int, start: int) -> _Cost[int]:
        """Emit the last level's two leaves in one loop over its bit."""
        spelling, bit_cell = self.spelling, 2 * self.perm[self.n - 1]
        leaf = spelling.leaf or spelling.one
        if self.table[combo] == "1":
            self.move(self.result)
            self.emit(leaf)
        self.move(bit_cell)
        self.emit(spelling.opener)
        skipped = self.count - start
        self.emit(spelling.zero)
        self.move(self.result)
        self.emit(
            leaf
            if self.table[combo + 1] == "1"
            else spelling.unleaf or spelling.decrement
        )
        self.move(bit_cell)
        self.emit(spelling.closer)
        return _Cost(max(skipped, self.count - start + self.retest))

    def two_sided(self, i: int, combo: int, one: int, start: int) -> _Cost[int]:
        """Raise flag_i, take the one-side on bit_i, else the zero-side on it."""
        spelling, flg = self.spelling, self.flag(i)
        self.move(flg)
        self.emit(spelling.one)  # flag_i = 1 (it is 0 by invariant)
        self.move(2 * self.perm[i])
        self.emit(spelling.opener)
        one_start = self.count
        self.emit(spelling.zero)  # clear the tested one-bit
        self.move(flg)
        self.emit(spelling.zero)  # clear the flag after selecting the one-side
        body_start = self.count
        one_cost = self.branch(i, one)
        one_flat = self.count - body_start
        self.move(2 * self.perm[i])
        self.emit(spelling.closer)  # bit is 0 now, so this exits
        one_cost = _Cost(self.count - one_start - one_flat + self.retest, (one_cost,))
        between = self.count
        span, zero_cost, zero_start = self.guarded(flg, i, combo)
        common = one_start - start + zero_start - between
        return _Cost(common, (one_cost, _Cost(span, (zero_cost,))))

    def emit_all(self) -> tuple[str, int]:
        """Emit the tree, then each deferred block's dispatch stage."""
        tree_cost = self.node(0, 0)
        stages = []
        for i, (depth, row) in enumerate(self.blocks):
            tail_start = self.count
            pending = self.flag(self.pending_levels[i])
            self.move(pending)
            dispatch_test = self.count - tail_start + 1
            self.emit(self.spelling.opener + self.spelling.zero)
            body_start = self.count
            del self.selected[depth, self.ids[depth][row >> (self.n - depth)]]
            body_cost = self.node(depth, row)
            body_flat = self.count - body_start
            self.move(pending)
            self.emit(self.spelling.closer)
            active = self.count - tail_start - body_flat + self.retest
            stages.append((i, body_cost, active, dispatch_test))

        tail_start = self.count
        self.move(self.result)
        tails: dict[int | None, int] = {None: self.count - tail_start}
        # Each emitted branch is evaluated once; deeper dispatch continuations
        # have already been priced when its definition is reached in reverse.
        for i, body_cost, active, skipped in reversed(stages):
            cost = active + body_cost.evaluate(tails)
            tails = {target: value + skipped for target, value in tails.items()}
            tails[i] = cost
        return "".join(self.parts), tree_cost.evaluate(tails)
