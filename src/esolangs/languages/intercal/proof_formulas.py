"""Executed command and snapshot-bit bounds."""


def execution(n: int, _: str) -> int:
    """N + 3 fixed, at most n - 3 named negations, and the named shared nodes.

    Edges into levels 1..l number Q_l - 1 + M_l <= 2Q_{l-1}, so r levels
    below the root name at most 2^(r-1); the last two levels hold 2 and 12.
    A level of width w holding q_l nodes names at most N + 1 - 2w in all,
    N the node count; the last levels hold 2, 12, 240 (the 240 pairs of
    level n - 3) and 65,280 (level n - 4), so the widest level is 2^(n-5)
    to n = 21 and 2^(n-6) from 22.  Exact for n <= 25 (witnesses build
    that far; n <= 4 exhaustive, naming 0, 0, 2, 3 nodes); equal to the
    bound to n = 38, past it the next level's cap makes this an upper bound.
    """
    if n <= 4:
        return (4, 5, 8, 11)[n - 1]
    t = 1 << n
    if n <= 21:
        return 2 * n + min((t >> 3) + 2, (t >> 4) + 14, (t >> 5) + 254)
    return 2 * n + (t >> 6) + (1 << 16) - 2


def workspace(n: int, _: str) -> int:
    """Nine bits and a key per variable, S the Execution statement bound."""
    bl = int.bit_length
    s = execution(n, "")
    return 9 * s - 18 + sum(map(bl, range(1, s - 1))) + bl(s)
