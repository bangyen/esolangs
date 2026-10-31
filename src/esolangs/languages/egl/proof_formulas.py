"""Snapshot-bit bounds."""


def _egl(n: int, p: str) -> int:
    """Grid, loop stack and cursor; ``d`` is the digit count of T."""
    bl = int.bit_length
    d = len(str(1 << n))
    return (
        3 * (1 << n) + 2 * n + 10 + bl(len(p) - d - 3) + bl(len(p) - d - 9) + 2 * bl(n)
    )


def workspace(n: int, p: str) -> int:
    """The stated workspace bound, evaluated for n and the program."""
    return _egl(n, p)
