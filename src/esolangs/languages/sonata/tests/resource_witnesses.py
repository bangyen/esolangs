"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _low_one


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_low_one(n),)
