"""Snapshot-bit bounds."""

bl = int.bit_length


def _depth(n: int) -> int:
    """Entries a deque holds is ``2 ** depth``: the generator's ``(n + 1) // 2``."""
    return (n + 1) // 2


def _rail(n: int, k: int) -> int:
    """Width of level k's bypass: cursor rails ``< ]─``, then pop pairs."""
    if k < n - _depth(n):
        return 4 << (n - _depth(n) - 1 - k)
    return 12 << (n - 2 - k)


def _switch(n: int, k: int) -> int:
    """Column of level k's switch: the last is 56, each level adds 36 + its rail."""
    return 56 + 36 * (n - 1 - k) + sum(_rail(n, j) for j in range(k, n - 1))


def workspace(n: int, _: str) -> int:
    """Peak written bits of the T - 1 run layout, row T - 4, n >= 3.

    The pointer's exit memory keeps an entry per node left and path cell
    passed, keyed by its column from the west end, 4 bits a heading.  A one
    walks its level's whole rail; a zero beats that only at the lone
    one-rail level ``n - depth - 1`` (+11 bits) and the last (+10).  The
    deques peak after the preload.
    """
    t = 1 << n
    arm = [51 - 4 * i for i in range(12)]
    cols = sum(bl(a) + bl(a - 1) for a in arm) + 2 * bl(56) + bl(57)
    entries = 27
    for k in range(n):  # the skips east of every switch
        s = _switch(n, k)
        count = 1 if k == 0 else 8
        cols += sum(bl(s + 3 + 4 * i) + bl(s + 4 + 4 * i) for i in range(count))
        entries += 2 * count
    zero = n - _depth(n) - 1
    s = _switch(n, zero)  # the one-rail level, a zero
    cols += bl(s) + bl(s + 1) + bl(s) + bl(s - 1) + bl(s - 4) + 2 * bl(s - 5)
    entries += 7
    for k in range(n - 1):  # a one: every column from the junction
        if k != zero:
            s, w = _switch(n, k), _rail(n, k)
            cols += sum(map(bl, range(s - w - 1, s + 1)))
            entries += w + 2
    d = _switch(n, 0) + 7  # the preload's tiles from the west
    tiles: list[int] = []  # the alternating worst table, execution order
    last = ""
    for i, bit in enumerate("10" * (t // 2 - 1) + "01"):
        tiles += [4] * (bit != last) + [6]
        last = bit
        if (i + 1) % (1 << _depth(n)) == 0 and i + 1 < t:
            tiles.append(4)
    tiles.reverse()
    for w in tiles:
        cols += bl(d) + bl(d + 1)
        d += w
    entries += 2 * len(tiles) + 1
    cols += bl(d)
    deque = sum(max(bl(i), 1) + (1 << _depth(n)) for i in range(t >> _depth(n)))
    return 4 * entries - 1 + cols + 13 + n - _depth(n) + deque + 2 * bl(n) + 17
