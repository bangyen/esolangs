"""Crement's emitted lines: three a shared node, the header and testers."""


def _lines(n: int, _: str) -> int:
    """N = 3P + 2n + 3, P the most unequal-halves nodes summed over levels."""
    shared = sum(
        min(1 << k, 4 ** (1 << (n - k - 1)) - 2 ** (1 << (n - k - 1))) for k in range(n)
    )
    return 3 * shared + 2 * n + 3


FORMULAS = {"scaling": (_lines, True, (3, 4, 5))}
