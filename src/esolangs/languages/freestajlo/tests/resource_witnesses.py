"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _freestajlo_worst, _low_one


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_freestajlo_worst(n), _low_one(n))
