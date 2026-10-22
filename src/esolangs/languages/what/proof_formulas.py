"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Tape, row-independent string and counters; k = min(n, 15) low inputs."""
    bl = int.bit_length
    k = min(n, 15)
    tokens = 6 * (1 << n) + (6 * n + 5 if n <= 15 else 9 * 2 ** (n - 15) + n + 134)
    wide = max(20, 2 * k - 2 + (n > 15))
    return (
        256
        + k * (k - 1)
        + wide
        + 8 * (n - k)
        + bl(tokens)
        + bl(2 * k + 1)
        + bl(2 * n - 1)
    )
