"""Streetcode's emitted area: the tree below five inputs, the race from five."""


def _gap(n: int) -> int:
    """G: the flat street's mouth spacing, 51 columns or the room, per level."""
    return sum(max(51, 2 ** (k - 1) + 3) for k in range(1, n))


def _cells(n: int, _: str) -> int:
    """The shipped area at its widest.

    n <= 4: the tree alone, 4 rows a leaf, every leaf distinct (parity), 8n + 20
    columns.  From 5 the flat street, 9 rows of T + m + 108 + G columns with m
    the minority entries marked (at most T/2: the zeros are marked when they are
    fewer than the ones by two), races the tree: the worst is a balanced
    table the tree does not beat.
    """
    if n < 5:
        return (32 * n + 80) << n
    return 9 * (3 * 2 ** (n - 1) + 108 + _gap(n))


FORMULAS = {"scaling": (_cells, True, (2, 3, 4, 5, 6, 7, 8, 9, 10))}
