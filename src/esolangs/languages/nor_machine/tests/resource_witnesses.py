"""Witnesses for the written workspace bound."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Reach the queue peak with all inputs essential and maximal runs."""
    if n < 4:
        return (("01", "1011", "11101111")[n - 1],)
    return ("10" * ((1 << (n - 1)) - 1) + "11",)
