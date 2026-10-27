"""ROTfuck's emitted characters: a lone-zero strip, then the rotated tail."""

#: The builder's padding of the second digit's walk, by its stride, checked
#: against the builder to n = 12; a stride-2 walk needs none.
_WALK_PAD = {2: 0, 4: 13, 8: 17, 16: 41, 32: 73, 64: 153, 128: 297}


def _chars(n: int, _: str) -> int:
    """3T - 2 for the strip, then the rotated select and read-out.

    The strip (2T - 1 moves, T - 1 ones) has no bracket, so it is never
    padded, and the tail is one text for every table whose inputs all matter.
    A digit reads in 49 characters for its first bit and 70 for each later
    one, then walks 3 * stride + 7, the stride doubling per bit below it;
    the short digit goes lowest.  The read-out is 50, and the builder pads
    9 an input + 3 plus the top walk's share.
    """
    assert n <= 12, "a third digit's walk is unpriced"
    tail = 50 + 9 * n + 3
    widths = ([n % 6] if n % 6 else []) + [6] * (n // 6)
    shift = 0
    for width in widths:
        tail += 49 + 70 * (width - 1) + 3 * (2 << shift) + 7
        shift += width
    tail += _WALK_PAD[2 << (n - widths[-1])]
    return 3 * (1 << n) - 2 + tail


FORMULAS = {"scaling": (_chars, True, tuple(range(2, 11)))}
