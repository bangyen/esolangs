"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _diagram_witness
from tests.proofs._witnesses import _morse, _one_i_swapped


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        (
            _morse("1000", "0010", n),
            _one_i_swapped(n),
            *_diagram_witness("one_i", n, top=27, bottom=2),
            *_diagram_witness("one_i", n, top=27, name="workspace_witness", bottom=2),
        )
        if n >= 2
        else ()
    )
