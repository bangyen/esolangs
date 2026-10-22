"""Back's emitted cells: the comb, then the smaller of it and the fold."""


def _comb(n: int) -> int:
    """3n + 5 load columns by max(6n - 1, 3T/4 + 1) rows (Rudin-Shapiro's tree)."""
    return (3 * n + 5) * max(6 * n - 1, 3 * (1 << n) // 4 + 1)


def _fold(n: int) -> int:
    """The H-tree fold's rectangle under the load row; parity reaches it.

    Five-level combs at the leaves; a node is 3 + max(H0, H1) wide and
    W0 + W1 + 2 tall, children transposed.
    """
    width, height, entry = 17, 32, 0  # the five-level comb, 3 * 5 + 2 wide
    for _ in range(6, n + 1):
        width, height, entry = 3 + height, 2 * width + 2, width + 1
    return (1 + width) * (max(0, 4 * n - entry) + height)


def _cells(n: int, _: str) -> int:
    """F: the comb to n = 5, then min(comb, fold), under 27.5T; reached to n = 6."""
    return _comb(n) if n <= 5 else min(_comb(n), _fold(n))


FORMULAS = {"scaling": (_cells, False, (3, 4, 5, 6, 7, 8, 9, 10))}
