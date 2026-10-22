"""Befunge's emitted cells: 80 columns by r rows, a header row then the table."""


def _ceil(a: int, b: int) -> int:
    return -(-a // b)


def _cells(n: int, _: str) -> int:
    """N = 80r: r = 1 + ceil(T/80) rows to n = 10, then 14, 15, 20.

    Below n = 7 the widest row is the header (5n + 28) or the 64-cell table.
    Past n = 10 the header folds or the table packs.
    """
    if n == 1:
        return 50  # the natural layout, 25 columns by two rows
    if n <= 10:
        return (1 + _ceil(1 << n, 80)) * max(5 * n + 28, min(1 << n, 80))
    # Past ten inputs: one input ignored keeps the plain 1024-cell table,
    # whose header (2n + 58 cells) folds past 80; all essential is packed.
    reads = 2 * n + 30
    if reads + 28 <= 80:
        plain = 80 * (1 + _ceil(1024, 80))
    else:
        plain = 80 * (_ceil(reads + 34, 78) + _ceil(1024, 80))
    rows = _ceil(5 * n + 64, 78)
    return max(plain, 80 * (rows + _ceil(_ceil(1 << n, 6), 80)))


FORMULAS = {"scaling": (_cells, True, (7, 8, 9, 10, 11, 12, 13))}
