"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _thisthat_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_thisthat_worst(n),) if n >= 3 else ()
