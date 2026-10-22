"""Streetcode's emitted characters: nine street rows of the lone-zero table."""


def _chars(n: int, _: str) -> int:
    """S: nine rows of the lone-zero street, or a tree of smaller area."""
    g = sum(max(51, 2 ** (k - 1) + 3) for k in range(1, n))
    area = 9 * (2 * 2**n + 107 + g)
    return area + area // (4 * n + 16)


FORMULAS = {"scaling": (_chars, False, (6, 7, 8))}
