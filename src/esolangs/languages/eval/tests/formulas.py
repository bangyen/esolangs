"""Eval's largest Gray-layout lookup, reached by full-support parity."""


def _chars(n: int, _: str) -> int:
    """One-stack through five; the two-stack literal's maximum one-run count."""
    t = 1 << n
    return 2 * t + 7 * n if n < 6 else 7 * t // 4 + 9 * n + 1


FORMULAS = {"scaling": (_chars, True, (4, 6))}
