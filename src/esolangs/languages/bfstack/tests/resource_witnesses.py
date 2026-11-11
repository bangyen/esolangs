"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _bfs_chars, _diagram_witness
from tests.proofs._witnesses import _bfstack_worst, _bfstack_ws_worst


def _named_witnesses(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_bfs_chars(n), *_diagram_witness("bfstack", n, 5))


def resource_corpus(n: int) -> tuple[str, ...] | None:
    """Return the named corpus when the general sweep is unnecessary."""
    if n >= 10:
        # Lower arities sweep the generic families; this named witness reaches
        # the one-arm chain bound without repeating them.
        return (_bfstack_worst(n), _bfstack_ws_worst(n))
    return None


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional cases in the order used for resource measurement."""
    tables: tuple[str, ...] = ()
    if n >= 8:
        tables += (_bfstack_worst(n),)
    if n >= 9:
        tables += (_bfstack_ws_worst(n),)
    tables += _named_witnesses(n)
    return tables
