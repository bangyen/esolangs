"""Trml witnesses for the exact source bound."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Toggle the final input on conjunction of the earlier inputs."""
    if n < 3:
        return ()
    return ("01" * ((1 << (n - 1)) - 1) + "10",)
