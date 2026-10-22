"""Dig's emitted area: the dense table's alternating layout, a fixed box per n."""


def _cells(n: int, _: str) -> int:
    """A: leaf rectangles are table-independent, and each two inputs map
    (rows, cols) -> (2 rows + 1, 2 cols + 1) from (35, 27) at n = 7, (55, 35) at 8.
    """
    k = 1 << ((n - 7) // 2)
    return (36 * k - 1) * (28 * k - 1) if n % 2 else (56 * k - 1) * (36 * k - 1)


FORMULAS = {"scaling": (_cells, True, (7, 8))}
