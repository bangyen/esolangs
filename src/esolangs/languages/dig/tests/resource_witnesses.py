"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _dig_indexed_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_dig_indexed_worst(n),) if 8 <= n <= 12 else ()
