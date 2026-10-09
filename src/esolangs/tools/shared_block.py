"""Select one repeated residual from the tree that survives sibling folding."""

from esolangs.tools.helpers import subtree_ids


def repeated_block(table: str) -> tuple[int, int] | None:
    """Return (depth, first row) with greatest repeated-span saving, or None."""
    ids = subtree_ids(table)
    n = len(ids) - 1
    live = {ids[0][0]: (1, 0)}
    best: tuple[int, int] | None = None
    saved = 0
    for depth in range(n):
        span = 1 << (n - depth)
        following: dict[int, tuple[int, int]] = {}
        for key, (copies, row) in live.items():
            if key < 2:
                continue
            saving = (copies - 1) * span
            if span >= 4 and saving > saved:
                saved, best = saving, (depth, row)
            block = row // span
            zero, one = ids[depth + 1][2 * block : 2 * block + 2]
            children = (
                [(zero, row)] if zero == one else [(zero, row), (one, row + span // 2)]
            )
            for child, first in children:
                previous, first = following.get(child, (0, first))
                following[child] = (previous + copies, first)
        live = following
    return best


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
