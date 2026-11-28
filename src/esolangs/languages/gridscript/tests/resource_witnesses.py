"""Full-support packed tables with five-digit chunk tokens."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Keep the high bit of every chunk and every input essential."""
    if n == 1:
        return ("10",)
    return ("1" * ((1 << n) - 2) + "01",)
