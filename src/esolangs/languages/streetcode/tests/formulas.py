"""Streetcode's emitted area: nine street rows of the lone-zero flat street."""


def _cells(n: int, _: str) -> int:
    """S: the flat street's area at its widest (lone zero); the shipped one is a min."""
    g = sum(max(51, 2 ** (k - 1) + 3) for k in range(1, n))
    return 9 * (2 * 2**n + 107 + g)


FORMULAS = {"scaling": (_cells, False, (6, 7, 8))}
