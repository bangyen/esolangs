"""Named witnesses for the generated resource bounds."""

from tests.proofs._witness_builders import _sbleq_worst
from tests.proofs._witnesses import SparseRows


def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (_sbleq_worst(n),) if n >= 11 else ()


def sparse_rows(n: int) -> SparseRows:
    """The packed witness's rows, as many as the band affords.

    A row's price is its chunk scan, and the scan's prices are
    chunk-value-driven, not positional (measured per row in the
    landing notes; a case's steps run at ~0.5M/s on a quiet box,
    degrading to ~0.2M/s under a memory-bound co-tenant — the
    sets are budgeted at the degraded rate, against the slow
    band's 600 s hard stop).
    {0, width/2, last} totals 37M steps at n = 21 and stays; at
    22 the middle row alone costs 44M, so {0, last} (34M) stands;
    at 23 every row past chunk 0 costs 60M or more, so chunk 0's
    last bit joins row 0 (12M together).  From n = 24 the chunks
    are 8-digit decimals and row 0 alone costs 40M steps; every
    second row measured there (57M and up) prices its pair past
    the band, so row 0 stands alone.  The dearer rows are
    recorded in the landing notes, unregistered.
    """
    width = 1 << n
    if n == 21:
        rows = (0, width // 2, width - 1)
    elif n == 22:
        rows = (0, width - 1)
    elif n == 23:
        rows = (0, n - 1)
    else:
        rows = (0,)
    return SparseRows(_sbleq_worst(n), rows, rows[-1])
