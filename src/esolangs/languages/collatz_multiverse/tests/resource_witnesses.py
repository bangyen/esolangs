"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _collatz_chars_worst
from tests.proofs._witnesses import _collatz_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_collatz_worst(n), _collatz_chars_worst(n)) if n >= 3 else ()
