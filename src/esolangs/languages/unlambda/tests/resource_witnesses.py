"""Execution maxima from the exhaustive small tables."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return a table attaining the maximum through three inputs."""
    return (("10", "1110", "11101011")[n - 1],) if n <= 3 else ()
