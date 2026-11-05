"""Exact default source maximum of the complete folded binary table."""


def _chars(n: int, _: str) -> int:
    """A non-symmetric all-one table except one off-diagonal zero attains it.

    All inputs are essential and P=T-1. Ignored reads reduce the grid and
    replace a weighted guard by x; counted tables have only m+1 cells.
    """
    size = 1 << n
    if n <= 3:
        return 3 * size + 25 * n + len(str(size)) + 8
    columns = 1 << min(n, (n + 3) // 2)
    blocks = size // columns
    return (
        2 * size
        + columns
        + 5 * blocks
        + 25 * n
        + len(str(columns))
        + len(str(3 * blocks))
        + 1
    )
