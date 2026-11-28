"""Named witnesses for the generated resource bounds."""


# One-cell runs at both ends: neither corridor direction shortens it (size);
# the balanced full corridor paints its most expensive addresses.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    half = 1 << (n - 1)
    return (
        (
            "0" + "1" * ((1 << n) - 2) + "0",
            "110" + "1" * ((1 << n) - 4) + "0",
            "10" + "1" * (half - 2) + "0" * (half - 2) + "10",
        )
        if n >= 3
        else ()
    )
