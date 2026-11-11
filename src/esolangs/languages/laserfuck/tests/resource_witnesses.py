"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import _laserfuck_worst
from tests.proofs.deep.execution import _dense
from tests.support.witness_tables import parity as _parity


# Below five its generic families miss the area worst by a column.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return _laserfuck_worst(n) if n < 5 else ()


def resource_corpus(n: int) -> tuple[str, ...] | None:
    """Return the named corpus when the general sweep is unnecessary."""
    width = 1 << n
    if n >= 5:
        # Retain prior extremes and include the shifted tape's exact witness.
        return (_parity(n), _dense(n), "0" * width, "1" * width, *_laserfuck_worst(n))
    return None
