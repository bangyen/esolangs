"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _false_tiled


# Six random subtables tiled by 4 random top inputs: the diagram wins and
# stores the full 26 lambdas, the variables' peak.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_false_tiled(n),) if n >= 9 else ()
