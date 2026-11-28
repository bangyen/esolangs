"""Tubes witnesses for the exact resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Maximize grid width and omit a minimum-width memory address."""
    ones = "1" * ((1 << n) - 2)
    return ("10" + ones, ones + "01")
