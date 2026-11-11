"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _subleq_packed_worst, _subleq_worst


# n = 9..14: the hashed table ships the packed decoder at its widest.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        *((_subleq_worst(n),) if n >= 3 else ()),
        *((_subleq_packed_worst(n),) if n >= 9 else ()),
    )
