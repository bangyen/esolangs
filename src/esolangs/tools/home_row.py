"""Boolean template generator for home row."""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    read_at,
)

__all__ = ["HOME_ROW_PAIR", "home_row"]


HOME_ROW_PAIR = ("s", "j")


def home_row(truth_table: str) -> str:
    """Return a Home Row template for a binary, MSB-first ``2**n`` truth table.

    Setters clear or preserve a fresh one; position-stable l/s/l gates add
    binary weights without nested loops. Guarded leaves count the index down
    onto a zero cell, printing at the selected row and skipping the rest.
    Rows agreeing with the final answer share its unguarded leaf.
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
        "a" + run + "lsffff" + "a" * weights.get(i, 0) + "fl"
        for i, run in enumerate([TEMPLATE_CHAR * len(HOME_ROW_PAIR[0])] * n)
    ]
    guarded = table.rstrip(table[-1])
    # Nothing after the last guard reads the index: it need not decrement.
    leaves = [
        "l" + "s" * (row < len(guarded) - 1) + "flffl" + "a" * (bit == "1") + "k;lff"
        for row, bit in enumerate(guarded)
    ]
    # The source's end halts, so the last answer needs no ``;``.
    last = ("ff" if guarded else "f") + "a" * (table[-1] == "1") + "k"
    return setup + "".join(bit_lines) + "ffff" * bool(guarded) + "".join(leaves) + last
