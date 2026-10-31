"""Befunge's emitted cells: 80 columns by r rows, a header row then the table."""


def _ceil(a: int, b: int) -> int:
    return -(-a // b)


def _cells(n: int, _: str) -> int:
    """N = 80r: r = 1 + ceil(T/80) rows to n = 7, then packed from n = 8.

    Below n = 7 the widest row is the header (5n + 28) or the 64-cell table.
    From n = 8 the six-bit packed grid is smaller (it ties at n = 7).
    """
    if n == 1:
        return 50  # the natural layout, 25 columns by two rows
    if n <= 7:
        return (1 + _ceil(1 << n, 80)) * max(5 * n + 28, min(1 << n, 80))
    return 80 * (_ceil(5 * n + 64, 78) + _ceil(_ceil(1 << n, 6), 80))


FORMULAS = {"scaling": (_cells, True, (7, 8, 9, 10, 11, 12, 13))}
