"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _boolfuck_flip
from tests.support.witness_tables import parity as _parity


# Parity with row 0 flipped: a symmetric count table, one flip short.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        *(("01101011",) if n == 3 else ()),
        "1" + _parity(n)[1:],
        *(("0000000010010110",) if n == 4 else ()),
        *((_boolfuck_flip(n),) if n >= 3 else ()),
    )
