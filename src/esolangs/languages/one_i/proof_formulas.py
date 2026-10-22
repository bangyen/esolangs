"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Snapshot bits of the worst row: frame + stack + input position, by range."""
    bl = int.bit_length
    io = bl(2 * n - 1)
    if n == 1:
        return 23
    if n <= 13:
        # s: largest start of a depth n-2 node; the literal pair sits at s and s+10,
        # the last frame at s+13; offsets cost bits and bl(0) is one bit.
        s = 37 * 2 ** (n - 2) - 3 * n - 31
        return 40 + (bl(s) or 1) + bl(s + 10) + bl(s + 13) + io
    if n <= 24:
        # a depth-3 node with maximal zero siblings (n+4 bits) pushes a constant
        # one level down: frame pc n+2, 4 bits of frame pc become bl(n+2)
        return 3 * n + 48 + bl(n + 2) + io
    # a constant half (bare B x (n-1), 4 bits each) outweighs the node terms
    return 5 * n - 1 + bl(n + 5) + io
