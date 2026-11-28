"""Named witnesses for small CV(N)(C) resource maxima."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return execution and size maximizers from exhaustive measurements."""
    return {
        1: ("10",),
        2: ("1110", "1001"),
        3: ("11111110", "10101001"),
    }.get(n, ())
