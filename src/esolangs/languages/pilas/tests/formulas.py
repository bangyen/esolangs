"""Command maxima, retaining the one-input boundary outside the linear case."""


def _steps(n: int, _: str) -> int:
    """The inverted one-bit leaf takes 15 main commands and 14 idle commands."""
    return 29 if n == 1 else 46 * n - 21


FORMULAS = {"execution": (_steps, True, (1, 2, 3, 6))}
