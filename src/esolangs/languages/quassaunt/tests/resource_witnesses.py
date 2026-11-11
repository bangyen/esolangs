"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _diagram_witness
from tests.proofs._witnesses import _quassaunt_stack, _quassaunt_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        _quassaunt_worst(n),
        *((_quassaunt_stack(n),) if n >= 3 else ()),
        *_diagram_witness("quassaunt", n, 21),
    )
