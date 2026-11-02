"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """Tape, row-independent string and counters; k = min(n, 15) low inputs."""
    bl = int.bit_length
    k = min(n, 15)
    if n <= 15:
        # Horner's retained prefixes add n(n-1) bits over the zero tape;
        # the neighbouring ASCII answer adds five. No index copy remains.
        tokens = 5 * (1 << n) + 6 * n - 5
        return 256 + n * (n - 1) + 5 + bl(tokens) + 2 * bl(2 * n - 1)
    tokens = 5 * (1 << n) + 10 * 2 ** (n - 15) + n + 134
    return (
        256
        + k * (k - 1)
        + 29
        + 8 * (n - k)
        + bl(tokens)
        + bl(2 * k + 1)
        + bl(2 * n - 1)
    )
