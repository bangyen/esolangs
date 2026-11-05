"""Befunge default area across its one-row and general lookup regimes."""


def _ceil(a: int, b: int) -> int:
    return -(-a // b)


def _cells(n: int, _: str) -> int:
    """Worst natural projection/nibble row to eight, then an 80-column packed grid."""
    if n <= 7:
        return 2 * max(2 * n + 23, 4 * n + 10)
    if n == 8:
        return 128
    return 80 * (_ceil(5 * n + 64, 78) + _ceil(_ceil(1 << n, 6), 80))
