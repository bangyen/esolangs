"""Snapshot-bit bounds."""


def _crement(n: int, _: str) -> int:
    """The whole program; P bounds the shared nodes, N the instructions."""
    bl = int.bit_length
    p = sum(
        min(1 << k, (1 << (2 * (1 << (n - k - 1)))) - (1 << (1 << (n - k - 1))))
        for k in range(n)
    )
    m = 3 * p + 2 * n + 3
    return (
        2 * bl(m)
        + 32
        + bl(2 * n + 3)
        + 2 * n * (10 + bl(m - 1))
        + p * (28 + 3 * bl(2 * n + 2) + 2 * bl(m - 2))
    )


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _crement(n, p)
