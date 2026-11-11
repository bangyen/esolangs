"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _od_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_od_worst(n),) if n >= 2 else ()
