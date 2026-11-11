"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _morse


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_morse("1000", "1011", n),) if n >= 2 else ()
