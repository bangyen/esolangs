"""Executed command and snapshot-bit bounds."""

import math


def execution(n: int, p: str) -> float:
    """The stated execution bound, evaluated for n and the program."""
    return 17 + 4 * n + (n - 1) * (3 + math.sqrt(2 * len(p)))
