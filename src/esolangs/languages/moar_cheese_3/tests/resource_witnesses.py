"""Witnesses for packed queue and frame peaks."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Keep a packed 3 in the second half with every input essential."""
    return ("10" + "1" * ((1 << n) - 2),)
