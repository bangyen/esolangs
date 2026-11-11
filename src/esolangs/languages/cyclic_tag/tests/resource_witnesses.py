"""Named witnesses for the generated resource bounds."""


# A single interior one retains the full positional source maximum.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return ("01" + "0" * ((1 << n) - 2),) if n >= 2 else ()
