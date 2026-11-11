"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _eval_alternating_upper


# The two-stack build's worst: a run of ones per pair in the upper half.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_eval_alternating_upper(n),) if n >= 4 else ()
