"""Named witnesses for the generated resource bounds."""

from tests.support.witness_tables import parity as _parity


# Equal halves under parity: the root skip doubles a 3T/2 - 1 term.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_parity(n - 1) * 2,) if n >= 2 else ()
