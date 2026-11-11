"""Named witnesses for the generated resource bounds."""

from tests.proofs._witnesses import SparseRows


def sparse_rows(n: int) -> SparseRows:
    """Alternating answers: row 0 attains E, the last row W (past 15 inputs).

    Row 0 satisfies every change point's test; each block's first row ties
    it, the middle and last rows cost less (measured at n = 16, 17).
    """
    width = 1 << n
    rows = (0, 1 << 15, width // 2, width - 1)
    return SparseRows(
        "10" * (width // 2), tuple(dict.fromkeys(rows)), 0, ws_witness=width - 1
    )
