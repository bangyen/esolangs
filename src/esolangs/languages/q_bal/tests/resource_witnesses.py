"""Named witnesses for the generated resource bounds."""


# From arity two, OR uses every input and has N = 2^T - 2.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return ("0" + "1" * (2**n - 1),)
