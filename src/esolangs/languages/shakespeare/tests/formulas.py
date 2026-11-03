"""Shakespeare's packed chunks, with the one-input parity path."""


def _steps(n: int, _: str) -> int:
    """Packing uses at most ceil(T/64) assignments, plus reads and multiplies."""
    return 6 if n == 1 else 2 * n + ((1 << n) + 63) // 64 + 6


FORMULAS = {"execution": (_steps, True, (1, 2, 3, 5, 7, 8, 10))}
