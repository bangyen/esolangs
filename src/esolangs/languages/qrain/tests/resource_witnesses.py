"""Witness tables for Qrain's finite resource maxima."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return maximizers for execution, workspace and source size."""
    return {
        1: ("01", "10"),
        2: ("1110", "1010", "1001"),
        3: ("11111110", "10111011", "10010110"),
    }.get(n, ())
