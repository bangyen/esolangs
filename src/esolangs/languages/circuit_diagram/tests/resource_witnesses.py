"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _seeded
from tests.support.witness_tables import parity as _parity


def resource_corpus(n: int) -> tuple[str, ...] | None:
    """Return the named corpus when the general sweep is unnecessary."""
    width = 1 << n
    if n >= 8:
        # Parity reaches 2n+1 at n=8; dense tables exercise pool admission
        # and constants use only their clock gate.
        return (_seeded(n, 1), _parity(n), "1" * width)
    return None
