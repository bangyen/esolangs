"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _codesick_chars_worst
from tests.proofs._witnesses import _codesick_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_codesick_worst(n), _codesick_chars_worst(n)) if n >= 2 else ()
