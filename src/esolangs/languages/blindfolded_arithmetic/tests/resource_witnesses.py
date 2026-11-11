"""Named witnesses for the generated resource bounds."""

from tests.support.witness_tables import parity as _parity


# Half the rows set, so table and complement tie: T/2 + 1 ones under a
# clear top bit (n even), or T/2 ones under a "10" top digit (n odd).
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        "1" + _parity(n)[1:],
        "1" * (2 ** (n - 1) + 1) + "0" * (2 ** (n - 1) - 1),
        "1" * (2 ** (n - 1) - 1) + "0" * 2 ** (n - 1) + "1",
    )
