"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    bl = int.bit_length
    return (
        bl(min(10 * 2**n - 7, 1934) + 10)
        + 1
        + max(
            bl(n + 3),
            bl(49 * (max(min(2**k, 2**2 ** (n - k)) for k in range(n + 1)) - 1)),
        )
        + 2 * bl(n)
    )
