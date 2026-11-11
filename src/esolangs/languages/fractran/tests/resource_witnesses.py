"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _unequal_first


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_unequal_first(n),) if n >= 2 else ()
