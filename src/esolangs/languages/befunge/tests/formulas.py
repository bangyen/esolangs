"""Befunge's emitted characters: a header, then the table in rows of 80."""


def _ceil(a: int, b: int) -> int:
    return -(-a // b)


def _chars(n: int, _: str) -> int:
    """N: a header (5n + 28 cells), then the table in rows of 80.

    Past n = 10 the header folds or the table packs.
    """
    if n == 1:
        return 28  # the natural layout, two cells
    if n <= 10:
        return 5 * n + 28 + 2**n + _ceil(2**n, 80)
    # Past ten inputs: one input ignored keeps the plain 1024-cell table,
    # whose header (2n + 58 cells) folds past 80; all essential is packed.
    reads = 2 * n + 30
    head = reads + 28
    if head <= 80:
        plain = head + 1024 + 13
    else:
        rows = _ceil(reads + 34, 78)
        plain = 80 * _ceil(head, 78) + 1024 + rows + 12
    rows = _ceil(5 * n + 64, 78)
    data = _ceil(2**n, 6)
    packed = 80 * rows + data + rows + _ceil(data, 80) - 1
    return max(plain, packed)


FORMULAS = {"scaling": (_chars, True, (1, 2, 3, 10, 11, 12, 13))}
