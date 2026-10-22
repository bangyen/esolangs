"""Thisthat's emitted area in cells: the full H-tree, the DAG never larger."""


def _cells(n: int, _: str) -> int:
    """N = W x H: sides 16(2^k - 1) + 1 and + 3, with 2^k the n-even / n-odd split.

    Levels pitch 8 * 2^((n - l - 1) // 2) (span + 2 router steps); even l span
    the width, odd l the height (+ 2 for the loader row).
    """
    if n % 2 == 0:
        side = 16 * ((1 << n // 2) - 1)
        return (side + 1) * (side + 3)
    return (16 * ((1 << (n + 1) // 2) - 1) + 1) * (16 * ((1 << (n - 1) // 2) - 1) + 3)


FORMULAS = {"scaling": (_cells, True, (3, 4, 5, 6, 7, 8))}
