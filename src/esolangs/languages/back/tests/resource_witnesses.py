"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _back_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return _back_worst(n)
