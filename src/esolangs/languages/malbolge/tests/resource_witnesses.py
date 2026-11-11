"""Named witnesses for the generated resource bounds."""

import random

from tests.proofs._witness_builders import _malbolge_stub
from tests.proofs._witnesses import SparseRows
from tests.proofs.deep.execution import _dense


def resource_corpus(n: int) -> tuple[str, ...] | None:
    """Return the named corpus when the general sweep is unnecessary."""
    width = 1 << n
    # Straight-line code: all 10 tables tie at every n measured; the
    # all-zeros or alternating label reaches the longest stub.
    return (_dense(n), _malbolge_stub(n), "0" * width)


def _malbolge_symmetric(n: int) -> SparseRows:
    """One weight-class witness at seventeen: named rows, answers only.

    The table is constant on Hamming-weight classes, with the class
    vector drawn from ``Random(17018)`` (eighteen choices, both
    answers attained).  The named rows -- row 0, every single-bit
    row, the first row of every weight and the last two rows --
    probe every folded input and the stub's, attain every weight and
    both answers.  The evidence is about this one weight-class
    witness only: it supports no scaling or execution claim, nothing
    about non-symmetric seventeen-input tables, and it does not
    soften "seventeen is open" -- below seventeen the suites execute
    every row of every corpus table, here only these named rows run.
    The witness field names the last row; no formula column is
    claimed for Malbolge, so it attains nothing.
    """
    rng = random.Random(17018)
    classes = "".join(rng.choice("01") for _ in range(n + 1))
    table = "".join(classes[row.bit_count()] for row in range(1 << n))
    rows = [0]
    for row in (
        *(1 << j for j in range(n)),
        *((1 << w) - 1 for w in range(n + 1)),
        (1 << n) - 2,
        (1 << n) - 1,
    ):
        if row not in rows:
            rows.append(row)
    return SparseRows(table, tuple(rows), rows[-1])


def _malbolge_projection(n: int) -> SparseRows:
    """One projection witness at seventeen: 36 named rows, answers only.

    The witness is the sparse pricing's measured table (M7): a seeded
    sixteen-input table (``Random(17017)``; the pricing script drew two
    tables from the seed before it, so those draws are consumed here)
    lifted to seventeen by ignoring the last input, each answer then
    appearing under both values of that input.  The eighteen projected
    rows -- row 0, every single-bit row, the half-width row (already a
    single bit) and the last row -- probe every folded input, attain
    both answers and include the step worst (projected row 16, 5,686
    steps, the formula's pinned worst at sixteen); measured on the
    sixteen build they total 100,484 steps, so the lifted 36 rows
    total 200,968, about 0.9 s of stepping.  The evidence is about
    this one projection witness only: it supports no scaling or
    execution claim, nothing about non-projection seventeen-input
    tables, and it does not soften "seventeen is open" -- below
    seventeen the suites execute every row of every corpus table,
    here only these named rows run.
    """
    rng = random.Random(17017)
    for _ in range((1 << (n - 1)) + (1 << n)):
        rng.choice("01")
    base = "".join(rng.choice("01") for _ in range(1 << (n - 1)))
    table = "".join(bit * 2 for bit in base)
    projected = (0, *(1 << j for j in range(n - 1)), (1 << (n - 1)) - 1)
    rows = tuple(2 * row + bit for row in projected for bit in (0, 1))
    return SparseRows(table, rows, 2 * 16)


def sparse_rows(n: int) -> tuple[SparseRows, ...]:
    """The two seventeen-input witnesses: projection and weight-class.

    The projection witness follows; the weight-class witness is
    :func:`_malbolge_symmetric`.  Both are answers-only.
    """
    return _malbolge_projection(n), _malbolge_symmetric(n)
