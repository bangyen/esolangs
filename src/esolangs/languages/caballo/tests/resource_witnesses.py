"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _caballo_chain, _morse


# Parity is the size worst; the chain is the execution worst.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_morse("0110", "1001", n), _caballo_chain(n)) if n >= 2 else ()
