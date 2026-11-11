"""Named witnesses for the generated resource bounds."""


# One-cell runs at both ends: neither corridor direction shortens it (size);
# a leading run of two and one zero at the end (workspace).
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        (
            "0" + "1" * ((1 << n) - 2) + "0",
            "110" + "1" * ((1 << n) - 4) + "0",
        )
        if n >= 3
        else ()
    )
