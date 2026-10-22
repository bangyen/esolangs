"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Line index, the larger of the Horner and scaled stacks, the input cursor.

    The alternating table has T - 1 change points and ends 01, so it holds the
    most lines, the last Horner push ``a`` and the largest scaled product.
    """
    bl = int.bit_length
    t = 1 << n
    a = 8 * n - 7 + 2 * (n % 2)
    b = a + 6
    return (
        bl(2 * t + 6 * n + 3 + n % 2)
        + max(bl(a) + bl(a + 2) + n + 1, bl((b + 2 * t - 2) * (b + 2 * t - 1)))
        + bl(2 * n - 1)
    )
