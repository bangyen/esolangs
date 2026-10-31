"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Snapshot bits of the worst row: frame + stack + input position.

    The stack holds two ``("fn", offset)`` literals (16 bits and the offset) per
    branching level, 2(n-1) in all, then 13 bits of numbers in the last leaf's
    ``Biic+>p``; the frame holds that leaf's offset and a 3-bit command number.
    Offsets come from the left siblings at maximal length 25 * 2^k / 4 - 6: the
    root's first is 0 (1 bit), its second and the next first take n+2 bits, the
    remaining 2n-5 and the leaf's frame take n+3 (offsets pass 2^(n+2) from
    depth 2); at n = 3 the last offset stays at n+2 bits, so 104.
    """
    if n == 3:
        return 104
    return 2 * n * n + 36 * n - 23 + (2 * n - 1).bit_length()
