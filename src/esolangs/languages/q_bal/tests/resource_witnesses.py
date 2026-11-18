"""Named witnesses for the generated resource bounds."""


# OR: every input essential and N = 2^T - 2, as many digits as 2^T - 1.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return ("0" + "1" * (2**n - 1),)
