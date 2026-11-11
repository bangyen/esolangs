"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _suffolk_deep, _suffolk_worst


# From n = 7 the sweep's worst shares; swapped, it ships one shorter.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        (_suffolk_deep(n),)
        if n >= 13
        else (_suffolk_worst(n), *(("10" + _suffolk_worst(n)[2:],) if n >= 7 else ()))
        if n >= 3
        else ()
    )
