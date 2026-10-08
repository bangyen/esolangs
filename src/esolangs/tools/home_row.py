"""Boolean template generator for home row."""

from itertools import groupby

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

__all__ = ["HOME_ROW_PAIR", "home_row"]


HOME_ROW_PAIR = ("s", "j")


def _runs(rows: str) -> list[tuple[int, str]]:
    """Return ``(end, run)`` for each maximal run of equal characters in ``rows``."""
    out: list[tuple[int, str]] = []
    for _, group in groupby(rows):
        run = "".join(group)
        out.append(((out[-1][0] if out else 0) + len(run), run))
    return out


def home_row(truth_table: str) -> str:
    """Return a Home Row template for a binary, MSB-first ``2**n`` truth table.

    Setters clear or preserve a fresh one; position-stable l/s/l gates add
    binary weights without nested loops. Guarded leaves count the index down
    onto a zero cell, printing at the selected row and skipping the rest.
    Rows agreeing with the final answer share its unguarded leaf, and any
    other run of equal rows is one leaf behind ``js`` clamped decrements (n=7
    random -33.3%, tiled -39.8%, one half constant -29.7%, constant blocks
    -57.4%).  No goto: a leaf is never reached twice, so no repeat is shared.
    """
    n = _validate_truth_table(truth_table)
    # The leaf chain is up to 2**n leaves, so dropping an ignored input
    # halves the program; its gate stays with weight zero, so nothing moves
    # and no setter changes width.
    used = essential_inputs(truth_table, n)
    # A constant table depends on nothing and reduces to a one-input table,
    # never to the length-1 table, which is not a valid shape.
    table = truth_table if len(used) == n else read_at(truth_table, used or [0], n)
    weights = {i: 2 ** (len(used) - 1 - slot) for slot, i in enumerate(used)}

    setup = "aaaaaalsffaaaaaaaaffflf"
    bit_lines = [
        "a" + TEMPLATE_CHAR + "lsffff" + "a" * weights.get(i, 0) + "fl"
        for i in range(n)
    ]
    guarded = table.rstrip(table[-1])
    # A run of equal rows is one leaf behind ``js`` clamped decrements: ``j``
    # skips the ``s`` on a zero cell, so the index reaches the leaf as
    # ``max(index - (k - 1), 0)`` and the leaf's test lands on the run's rows.
    # Nothing after the last guard reads the index: it need not decrement.
    leaves = [
        "js" * (len(run) - 1)
        + "l"
        + "s" * (stop < len(guarded))
        + "flffl"
        + "a" * (run[0] == "1")
        + "k;lff"
        for stop, run in _runs(guarded)
    ]
    # The source's end halts, so the last answer needs no ``;``.
    last = ("ff" if guarded else "f") + "a" * (table[-1] == "1") + "k"
    return setup + "".join(bit_lines) + "ffff" * bool(guarded) + "".join(leaves) + last
