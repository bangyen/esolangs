"""The admitted bank bound and inline bound cover non-affine programs."""


def _execution(n: int, _: str) -> int:
    """The exhaustive three-input maximum, then the three proved form bounds."""
    if n == 3:
        return 65
    affine = 4 * n * n + 9 * n + 5 - 6 * (n // 2)
    bank = (3 * n * n + 3) // 4 + 20 * n + 4
    return max(22 * n, affine, bank)


FORMULAS = {"execution": (_execution, True, (3, 6))}
