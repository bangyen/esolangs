"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _diagram_witness
from tests.proofs._witnesses import _unequal_first


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        *((_unequal_first(n), *_diagram_witness("stisp", n, 20)) if n >= 2 else ()),
        *_diagram_witness("stisp", n, 7, "workspace_witness", bottom=1),
    )
