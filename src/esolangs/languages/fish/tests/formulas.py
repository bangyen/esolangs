"""Fish bounds: plain lookup to n = 5, the packed row from n = 6."""

bl = int.bit_length


def _column(least: int) -> tuple[int, int]:
    """The packed row's column and its literal's length (generator._column)."""
    k = -(-least // 15)
    if k <= 15:
        return 15 * k, 3
    m = bl(least)
    return 1 << m, 1 + 2 * m


def _packed(n: int) -> tuple[int, int]:
    """Column and literal length once the literal itself may move the column."""
    bare = 9 * n + 33
    start, lit = _column(bare + 6)
    if bare + 2 * lit > start:
        start, lit = _column(bare + 2 * lit)
    return start, lit


def _execution(n: int, _: str) -> int:
    """Straight-line code to the ``;``: 9 a read, then the lookup."""
    if n <= 5:
        return 9 * n + 9
    return 9 * n + 33 + 2 * _packed(n)[1]


def _workspace(n: int, _: str) -> int:
    """The ip at ``;``, the stack at its peak, the input and halted flag.

    Packed, ``,`` divides: the quotient is a 64-bit float.
    """
    if n <= 5:
        return bl(9 * n + 8) + n + 13 + bl(n)
    return bl(_execution(n, "") - 1) + bl(_packed(n)[0]) + bl(n) + 71


def _scaling(n: int, _: str) -> int:
    """Characters: header and table to n = 5, then the packed row.

    The packed row is its column, 6 powers and T/6 cells.
    """
    if n <= 5:
        return (1 << n) + 9 * n + 10
    return _packed(n)[0] + 6 - (-(1 << n) // 6)


FORMULAS = {
    "execution": (_execution, True, (3, 4, 5, 6, 7)),
    "workspace": (_workspace, True, (3, 4, 5, 6, 7)),
    "scaling": (_scaling, True, (3, 4, 5, 6, 7)),
}
