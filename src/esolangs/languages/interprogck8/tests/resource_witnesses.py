"""Named witnesses for the generated resource bounds."""

import importlib

from tests.proofs._witness_builders import _diagram_witness
from tests.proofs._witnesses import SparseRows


# An 8-row cluster whose root block hops 15 lines (a 33-character body, held
# by the slot and the calling frame), under equal-half reads.
def resource_tables(n: int) -> tuple[str, ...]:
    """Return additional truth tables for the resource ledger."""
    return (
        (
            "01100000" * (1 << n - 3),
            "1" + "".join(str(row.bit_count() % 2) for row in range(1, 1 << n)),
            *_diagram_witness("interprogck8", n, 10),
            *_diagram_witness("interprogck8", n, 8, "steps_witness"),
        )
        if n >= 3
        else ()
    )


def sparse_rows(n: int) -> SparseRows:
    """The steps witness; the all-ones row attains E, the rest stay under.

    n = 11: measured over all 2,048 rows, rows 2045-2047 reach the maximum
    37,997 = E.  n = 12: rows 4093-4095 reach 76,011 (of 4032-4095 measured).
    """
    owner = importlib.import_module("esolangs.languages.interprogck8.tests.formulas")
    width = 1 << n
    witness = width - 1
    rows = (0, 1, width // 2 - 1, width - 32, width // 2 - 16, width - 16, witness)
    return SparseRows(owner.steps_witness(n), tuple(dict.fromkeys(rows)), witness)
