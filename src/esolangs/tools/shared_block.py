"""Select repeated residuals from the tree that survives sibling folding."""

from __future__ import annotations

from dataclasses import dataclass

from esolangs.tools.helpers import subtree_ids


@dataclass(frozen=True, slots=True)
class ContinuationCost:
    """A local maximum plus its eventual normal or deferred continuation."""

    value: int
    children: tuple[ContinuationCost, ...] = ()
    target: int | None = None

    def evaluate(self, tails: dict[int | None, int]) -> int:
        """Return the worst reachable cost with the supplied continuations."""
        return self.value + (
            max(child.evaluate(tails) for child in self.children)
            if self.children
            else tails[self.target]
        )


def repeated_definitions(
    table: str, *, branching_only: bool = False
) -> tuple[tuple[int, int], ...]:
    """Return every repeated nonconstant residual in increasing depth order."""
    found = _repeated_blocks(table)
    if not branching_only:
        return tuple((depth, row) for depth, row, _ in found)
    ids = subtree_ids(table)
    n = len(ids) - 1
    return tuple(
        (depth, row)
        for depth, row, _ in found
        if ids[depth + 1][row >> (n - depth - 1)]
        != ids[depth + 1][(row >> (n - depth - 1)) + 1]
    )


def repeated_block(table: str) -> tuple[int, int] | None:
    """Return (depth, first row) with greatest repeated-span saving, or None."""
    found = _repeated_blocks(table)
    if not found:
        return None
    depth, row, _ = max(found, key=lambda block: block[2])
    return depth, row


def repeated_blocks(table: str) -> tuple[tuple[int, int], ...]:
    """Return the greatest repeated-span residual at each folded tree level."""
    best: dict[int, tuple[int, int]] = {}
    for depth, row, saving in _repeated_blocks(table):
        if depth not in best or saving > best[depth][1]:
            best[depth] = row, saving
    return tuple((depth, row) for depth, (row, _) in best.items())


def repeated_bank(
    table: str, *, reserve_last: bool = False, ranked: bool = True
) -> tuple[tuple[tuple[int, int], ...], tuple[int, ...]]:
    """Bank repeats by occurrence or copy count at the greatest-saving level."""
    n = len(table).bit_length() - 1
    groups: dict[int, list[tuple[int, int]]] = {}
    for depth, row, saving in _repeated_blocks(table):
        groups.setdefault(depth, []).append((row, saving >> (n - depth)))
    best: tuple[tuple[int, int], ...] = ()
    flags: tuple[int, ...] = ()
    greatest = 0
    for depth, group in groups.items():
        capacity = n - depth - reserve_last
        if capacity < 2 or len(group) < 2:
            continue
        if ranked:
            # Copy counts are bounded by 2**depth; counting buckets over all
            # levels cost sum(2**depth) = O(T), without sorting or a search.
            buckets: list[list[int]] = [
                [] for _ in range(max(copies for _, copies in group) + 1)
            ]
            for row, copies in group:
                buckets[copies].append(row)
            ordered = [
                (row, copies)
                for copies in range(len(buckets) - 1, 0, -1)
                for row in buckets[copies]
            ]
        else:
            ordered = group
        chosen = [(depth, row) for row, _ in ordered[:capacity]]
        saved = sum(copies << (n - depth) for _, copies in ordered[:capacity])
        if saved > greatest:
            greatest = saved
            best = tuple(chosen)
            flags = tuple(range(depth, depth + len(best)))
    return best, flags


def _repeated_blocks(table: str) -> list[tuple[int, int, int]]:
    ids = subtree_ids(table)
    n = len(ids) - 1
    live = {ids[0][0]: (1, 0)}
    found: list[tuple[int, int, int]] = []
    for depth in range(n):
        span = 1 << (n - depth)
        following: dict[int, tuple[int, int]] = {}
        for key, (copies, row) in live.items():
            if key < 2:
                continue
            saving = (copies - 1) * span
            if span >= 4 and saving > 0:
                found.append((depth, row, saving))
            block = row // span
            zero, one = ids[depth + 1][2 * block : 2 * block + 2]
            children = (
                [(zero, row)] if zero == one else [(zero, row), (one, row + span // 2)]
            )
            for child, first in children:
                previous, first = following.get(child, (0, first))
                following[child] = (previous + copies, first)
        live = following
    return found


type BranchCost = tuple[int | None, int | None]


def add_cost(cost: BranchCost, extra: int) -> BranchCost:
    """Add commands separately to normal and deferred paths."""
    normal, deferred = cost
    return (
        None if normal is None else normal + extra,
        None if deferred is None else deferred + extra,
    )


def merge_cost(a: BranchCost, b: BranchCost) -> BranchCost:
    """Take each path class's maximum, preserving absent classes."""

    def maximum(x: int | None, y: int | None) -> int | None:
        if x is None:
            return y
        return x if y is None else max(x, y)

    return maximum(a[0], b[0]), maximum(a[1], b[1])


def normal_cost(cost: BranchCost) -> int:
    """Return a completed tree's cost; abort if no ordinary path exists."""
    value = cost[0]
    if value is None:
        raise ValueError("completed tree has no ordinary path")
    return value


def dispatch_cost(prefix: BranchCost, active: int, skipped: int) -> BranchCost:
    """Combine disjoint prefix classes with their matching dispatch costs."""
    normal, deferred = prefix
    choices = []
    if normal is not None:
        choices.append(normal + skipped)
    if deferred is not None:
        choices.append(deferred + active)
    return max(choices), None
