"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _smu_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_smu_worst(n),)
