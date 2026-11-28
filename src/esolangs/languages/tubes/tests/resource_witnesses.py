"""Tubes witnesses for the exact grid and command bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """A single zero at row 1 forces positional indexing and a dense row."""
    return ("10" + "1" * ((1 << n) - 2),)
