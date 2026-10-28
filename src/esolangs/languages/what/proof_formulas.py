"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Tape, row-independent string and counters; k = min(n, 15) low inputs."""
    bl = int.bit_length
    k = min(n, 15)
    tokens = 5 * (1 << n) + (6 * n + 6 if n <= 15 else 10 * 2 ** (n - 15) + n + 134)
    # Through 15 inputs the index never wraps: a k-bit value, two of them
    # at the Horner step.  Past, the sentinel 65535 and the last row stay.
    wide = max(k + 4, 2 * k - 3) if n <= 15 else 29
    return (
        256
        + k * (k - 1)
        + wide
        + 8 * (n - k)
        + bl(tokens)
        + bl(2 * k + 1)
        + bl(2 * n - 1)
    )
