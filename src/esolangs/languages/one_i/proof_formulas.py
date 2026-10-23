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
        # Peaks add per component: stack 2n+44 (bit, two literals of 16 + n+4
        # bits; offsets stay under 37T/4 < 2^(n+4)) + frame n+4+bl(n+2) (a
        # depth-4 constant at an n+4 bit offset, body n+3 ops with the `$$`),
        # executed to n = 24 (row 11110000..); 4(n-1) of a depth-1 constant
        # overtakes at n = 25.
        return 3 * n + 48 + bl(n + 2) + io
    # a constant half (bare B x (n-1), 4 bits each) outweighs the node terms;
    # executed to n = 26 (any row opening 1: frame n+8, stack 4(n-1))
    return 5 * n - 1 + bl(n + 5) + io
