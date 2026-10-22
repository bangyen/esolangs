"""Snapshot-bit bounds."""

bl = int.bit_length


def _switch(n: int, k: int) -> int:
    """Column of level k's switch: the last is 56, each level adds 36 + 4c."""
    return 56 + 36 * (n - 1 - k) + 4 * ((1 << (n - 1 - k)) - 1)


def workspace(n: int, _: str) -> int:
    """Peak written bits of the T - 1 run layout, row T - 4, n >= 3.

    The pointer's exit memory keeps an entry per node left and path cell
    passed, keyed by its column from the west end, 4 bits a heading:
    7T + 18n + 5 entries.  The deques peak after the preload.
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
    s = _switch(n, n - 2)  # level n - 2, a zero
    cols += bl(s) + bl(s + 1) + bl(s) + bl(s - 1) + bl(s - 4) + 2 * bl(s - 5)
    entries += 7
    for k in range(n - 2):  # a one: every column from the junction
        s = _switch(n, k)
        c = 1 << (n - 2 - k)
        cols += sum(map(bl, range(s - 4 * c - 1, s + 1)))
        entries += 4 * c + 2
    d = _switch(n, 0) + 7  # the preload's tiles from the west
    tiles = [6, 6, 4] + [4, 6, 4, 6, 4] * (t // 2 - 1)
    for w in tiles:
        cols += bl(d) + bl(d + 1)
        d += w
    entries += 2 * len(tiles) + 1
    cols += bl(d)
    deque = sum(max(bl(i), 1) + 2 for i in range(t // 2))
    return 4 * entries - 1 + cols + 13 + n - 1 + deque + 2 * bl(n) + 17
