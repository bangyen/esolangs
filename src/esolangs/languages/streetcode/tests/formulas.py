"""Streetcode's emitted area: the tree below five inputs, the race from five."""


def _gap(n: int) -> int:
    """G: the flat street's mouth spacing, 51 columns or the room, per level."""
    return sum(max(51, 2 ** (k - 1) + 3) for k in range(1, n))


def _cells(n: int, _: str) -> int:
    """The shipped area at its widest.

    n <= 4: the tree alone, 4 rows a leaf, every leaf distinct (parity), 8n + 20
    columns.  From 5 the flat street, 9 rows of 2T - k + 108 + G columns with k
    zeros, races the tree (4 * (8n + 20) * (1 + sum_d min(2^d, k))): the worst is
    the flat at the least k where the tree is no smaller.
    """
    if n < 5:
        return (32 * n + 80) << n

    def flat(k: int) -> int:
        return 9 * (2 * 2**n - k + 108 + _gap(n))

    def tree(k: int) -> int:
        return 4 * (8 * n + 20) * (1 + sum(min(2**d, k) for d in range(n)))

    return flat(next(k for k in range(1, 2**n) if tree(k) >= flat(k)))


FORMULAS = {"scaling": (_cells, True, (2, 3, 4, 5, 6, 7, 8, 9, 10))}
