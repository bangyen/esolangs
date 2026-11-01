"""Snapshot-bit bounds."""


def workspace(n: int, _: str) -> int:
    """N - 1 forced thunks of 64 bits and their addresses, then the print block."""
    bl = int.bit_length
    return 64 * n + 306 + sum(map(bl, range(1, n))) + bl(n)


def execution(n: int, program: str) -> int:
    """Constants force n reads over floor(n/2)+1 blocks; otherwise match each bit."""
    if program.startswith("^:std::io=a;main:={"):
        return 3 * n + 3 * (n // 2) + 6
    return 8 * n + 5
