"""ROTfuck's emitted characters: a lone-zero strip, then the rotated tail."""


def _chars(n: int, _: str) -> int:
    """3T - 2 for the strip, then the rotated select and read-out.

    The strip (2T - 1 moves, T - 1 ones) has no bracket, so it is never
    padded, and the tail is one text for every table whose inputs all matter.
    A 6-bit digit reads in 49 characters for its first bit and 70 for each
    later one, then walks 3 * stride + 7 (strides 2, 128); the read-out is 50.
    The builder's padding, equal at all 8 phases and checked against it to
    n = 12: 9 an input + 3, and 297 once the stride-128 walk exists.
    """
    assert n <= 12, "a third digit's stride-8192 walk is unpriced"
    tail = 50 + 9 * n + 3 + 297 * (n >= 7)
    for shift in range(0, n, 6):
        tail += 49 + 70 * (min(6, n - shift) - 1) + 3 * (2 << shift) + 7
    return 3 * (1 << n) - 2 + tail


FORMULAS = {"scaling": (_chars, True, tuple(range(2, 11)))}
