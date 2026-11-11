"""Named witnesses for the generated resource bounds."""

from tests.support.witness_tables import parity as _parity


# The last input ignored: n - 1 essential inputs can outrun all n.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_parity(n - 1) * 2,) if n >= 3 else ()
