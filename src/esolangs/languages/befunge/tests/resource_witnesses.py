"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _befunge_worst
from tests.support.witness_tables import parity as _parity


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_befunge_worst(n),)


def resource_corpus(n: int) -> tuple[str, ...] | None:
    """Return the named corpus when the general sweep is unnecessary."""
    # Straight-line code over the inputs that matter; parity has all, and
    # the longest scaling text needs a layout parity misses at n = 11, 12.
    return (_parity(n), _befunge_worst(n))
