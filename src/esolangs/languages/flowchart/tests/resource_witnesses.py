"""Named witnesses for the generated resource bounds."""


# T - 1 runs: alternating but one equal pair.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return ("10" * (2 ** (n - 1) - 1) + "01",)
