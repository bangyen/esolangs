"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """N + 3 fixed, at most n - 3 named negations, and the named shared nodes.

    Edges into levels 1..l number Q_l - 1 + M_l <= 2Q_{l-1}, so r levels
    below the root name at most 2^(r-1); the last two levels hold 2 and 12.
    Exact for n <= 12; n <= 4 (exhaustive) name 0, 0, 2, 3 nodes, and past
    n = 12 the 240 pairs of level n - 3 cap it below this bound.
    """
    if n <= 4:
        return (4, 5, 8, 11)[n - 1]
    return 2 * n + min(((1 << n) >> 3) + 2, ((1 << n) >> 4) + 14)


def workspace(n: int, _: str) -> int:
    """Nine bits and a key per variable, S the Execution statement bound."""
    bl = int.bit_length
    s = execution(n, "")
    return 9 * s - 18 + sum(map(bl, range(1, s - 1))) + bl(s)
