"""Modulous's emitted characters: the literal and one weighted read an input."""


def _chars(n: int, _: str) -> int:
    """N = T + 82 + 48n + Σ_{k<n} digits(2^k): the weights are 1, 2, 4, ..."""
    return (1 << n) + 82 + 48 * n + sum(len(str(1 << k)) for k in range(n))


FORMULAS = {"scaling": (_chars, True, (3, 4, 5, 8))}
