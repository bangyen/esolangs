"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _diagram_witness, _switchcase_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        _switchcase_worst(n),
        *_diagram_witness("switchcase", n, 5, "workspace_witness", bottom=1),
    )
