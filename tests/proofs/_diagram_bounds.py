"""Most nodes a reduced decision diagram holds, level by level, for size bounds."""


def profile(n: int) -> tuple[list[int], list[int], list[int], list[int]]:
    """Return per-level ``(branching, equal-halved, constants, top id)`` maxima.

    A level k node sits at one of 2^k positions and is one of the 2^2^(n-k)
    subtables: ``branching`` has distinct halves, ``equal-halved`` is a
    nonconstant with equal halves, at most 2 constants take what is left.
    ``top`` bounds the ids of :func:`subtree_ids`, fresh bottom-up.
    """
    rows = [1 << (n - k) for k in range(n)]
    branching = [min(1 << k, (1 << rows[k]) - (1 << rows[k] // 2)) for k in range(n)]
    equal = [min((1 << k) - branching[k], (1 << rows[k] // 2) - 2) for k in range(n)]
    constants = [min(2, (1 << k) - branching[k] - equal[k]) for k in range(n)]
    nodes = [min(1 << k, (1 << rows[k]) - 2) for k in range(n)]
    top = [1 + sum(nodes[k:]) for k in range(n)]
    return branching, equal, constants, top


def digits(top: int, count: int) -> int:
    """Return the most decimal digits ``count`` distinct ids up to ``top`` hold."""
    return sum(len(str(i)) for i in range(top - count + 1, top + 1))
