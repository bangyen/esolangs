"""Named witnesses for HQ9+ with headers source size."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Clear row zero to produce the largest nonconstant literal."""
    return ("0" + "1" * ((1 << n) - 1),)
