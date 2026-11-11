"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _diagram_witness, _row_one


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        _row_one(n),
        *_diagram_witness("modulous", n, 8, "resource_witness", bottom=2),
    )
