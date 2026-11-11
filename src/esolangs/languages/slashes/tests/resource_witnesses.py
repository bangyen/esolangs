"""Named witnesses for the generated resource bounds."""


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        "10" if n == 1 else "10" * (2 ** (n - 1) - 1) + "11",
        "10111011" if n == 3 else "0" * (1 << n),
    )
