"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _intercal_chars_worst, _intercal_worst


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        (_intercal_worst(n), *((_intercal_chars_worst(n),) if n <= 23 else ()))
        if 3 <= n <= 25
        else ()
    )
