"""Executed command and snapshot-bit bounds."""

from math import isqrt

_VARIABLE_MAX = 65535  # the largest INTERCAL variable number


def _named(n: int) -> int:
    """The most named shared nodes (the Execution clause's M), for n >= 5."""
    t = 1 << n
    if n <= 21:
        return min((t >> 3) + 2, (t >> 4) + 14, (t >> 5) + 254)
    return (t >> 6) + (1 << 16) - 2


def _arrays(n: int, named: int) -> int:
    """DIMENSION statements for the P names past ``.65535``, highest 2n - 2 + named."""
    spilled = 2 * n - 2 + named - _VARIABLE_MAX
    return (spilled - 1) // (isqrt(spilled - 1) + 1) + 1 if spilled > 0 else 0


def _bl_sum(m: int) -> int:
    """``sum(map(int.bit_length, range(1, m + 1)))`` in closed form."""
    if m <= 0:
        return 0
    b = m.bit_length()
    return (b - 2) * (1 << (b - 1)) + 1 + b * (m - (1 << (b - 1)) + 1)


def execution(n: int, _: str) -> int:
    """N + 3 fixed, at most n - 3 named negations, the named shared nodes, and arrays.

    Edges into levels 1..l number Q_l - 1 + M_l <= 2Q_{l-1}, so r levels
    below the root name at most 2^(r-1); the last two levels hold 2 and 12.
    A level of width w holding q_l nodes names at most N + 1 - 2w in all,
    N the node count; the last levels hold 2, 12, 240 (the 240 pairs of
    level n - 3) and 65,280 (level n - 4), so the widest level is 2^(n-5)
    to n = 21 and 2^(n-6) from 22.  Exact for n <= 26 (witnesses build that
    far; n <= 4 exhaustive, naming 0, 0, 2, 3 nodes); equal to the bound to
    n = 38, past it the next level's cap makes this an upper bound.
    """
    if n <= 4:
        return (4, 5, 8, 11)[n - 1]
    named = _named(n)
    return 2 * n + named + _arrays(n, named)


def workspace(n: int, _: str) -> int:
    """Nine bits and a key per variable; past .65535 the spilled names cost less.

    Exact to n = 26: the written snapshot only grows and the statement
    index climbs, so the peak bits are the final snapshot's — each
    scalar a key of ``8 + bl(k)`` around a one-bit value, the scalars
    ``.1``..``.m``; past 20 the P spilled names fill A arrays of width
    ``isqrt(P - 1) + 1`` (key ``8 + bl(j)``, elements ``bl(i) + 1``
    0-based), checked against snapshots at 21, 22, 25 and text at 26.
    """
    bl = int.bit_length
    s = execution(n, "")
    named = _named(n) if n > 4 else 0
    spilled = 2 * n - 2 + named - _VARIABLE_MAX
    if spilled <= 0:
        return 9 * s - 18 + sum(map(bl, range(1, s - 1))) + bl(s)
    width = isqrt(spilled - 1) + 1
    arrays = _arrays(n, named)
    total = 9 * _VARIABLE_MAX + _bl_sum(_VARIABLE_MAX)  # the scalars .1..65535
    total += arrays * (8 + bl(width)) + _bl_sum(arrays)  # the ,j keys and widths
    full = width + 1 + _bl_sum(width - 1)
    last = spilled - (arrays - 1) * width
    return total + (arrays - 1) * full + (last + 1 + _bl_sum(last - 1)) + bl(s)
