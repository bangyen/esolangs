"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _diagram_witness


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        *_diagram_witness("bleh", n, 23),
        *_diagram_witness("bleh", n, 7, "workspace_witness", bottom=1),
    )
