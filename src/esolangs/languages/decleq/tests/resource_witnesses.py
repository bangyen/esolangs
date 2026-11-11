"""Named witnesses for the generated resource bounds."""


# A one closing each block of 2^k: n - 2 copy jumps in a row.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return ("".join("0" * (2**k - 1) + "1" for k in range(n - 1, 0, -1)) + "00",)
