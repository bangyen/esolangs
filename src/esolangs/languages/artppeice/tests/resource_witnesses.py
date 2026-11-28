"""Full positional lookups for exact resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Keep every weight and avoid zero entries in the first two passes."""
    return ("1" * ((1 << n) - 2) + "01",)
