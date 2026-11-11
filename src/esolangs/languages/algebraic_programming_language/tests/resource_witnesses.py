"""Named witnesses for the generated resource bounds."""

from tests.proofs.deep.execution import _dense
from tests.support.witness_tables import parity as _parity


def resource_corpus(n: int) -> tuple[str, ...] | None:
    """Return the named corpus when the general sweep is unnecessary."""
    width = 1 << n
    if n >= 8:
        # Lower arities sweep the full corpus; retain shared, dense and inline
        # program shapes for the larger frame/serial bounds.
        return (_parity(n), _dense(n), "0" * width, "1" * width)
    return None
