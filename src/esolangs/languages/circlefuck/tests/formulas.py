"""Circlefuck's emitted characters: the plain layout over c = ⌈n/7⌉ index cells."""


def _chars(n: int, _: str) -> int:
    """N = T + 52n + 10 + (c-1)(146 + 149(c-2)/2 + 2(n-7c+6)).

    Each cell past the first adds a deleter.
    """
    c = -(-n // 7)
    return (
        (1 << n)
        + 52 * n
        + 10
        + 146 * (c - 1)
        + 149 * (c - 1) * (c - 2) // 2
        + 2 * (c - 1) * (n - 7 * c + 6)
    )


FORMULAS = {"scaling": (_chars, True, (3, 5, 8, 9))}
