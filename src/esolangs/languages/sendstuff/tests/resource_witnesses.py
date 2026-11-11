"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _sendstuff_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_sendstuff_worst(n),) if n >= 3 else ()
