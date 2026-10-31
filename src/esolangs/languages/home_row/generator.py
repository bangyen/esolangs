"""Home Row Boolean program generator: a weighted index counted down a leaf chain.

Each input but the last essential one adds its binary weight to an index
cell; guarded leaves count it down onto a zero cell, printing at the selected
pair of rows and skipping the rest.  The last essential input sets two of four
flag cells (``48 + x``, ``49 - x``; the others hold 48 and 49), so a leaf
prints the flag its pair names: ``00``, ``11``, ``x`` or ``not x``.  Setters
clear or preserve a fresh one; position-stable l/s/l gates add binary weights
without nested loops.  Ignored inputs keep a zero-weight gate; a constant
table discards all setters and prints a literal.  No goto, and ``l`` re-runs
only its own block: no leaf of the linear chain is reached twice.

Size:
    Up to 2**(n-1) leaves in a linear chain; n=10 and: 703 chars (was 1,175),
    n=10 random 1847: 5,241 chars (was 8,711), n=10 parity: 4,773 chars (was
    10,359).

Decisions:
    A negated twin takes a table when shorter: ``and`` at n=8 543 -> 297.
    Sharing runs of equal pairs through ``js`` clamped decrements: see
    [ablations.run_sharing].
"""

from itertools import groupby

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.home_row.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape

__all__ = ["HOME_ROW_PAIR", "home_row"]


HOME_ROW_PAIR = ("s", "j")
_CONSTANT_SETUP = "aaaaaalsffaaaaaaaaffflf"
# Cell 0 is the index, cell 2 the gates' scratch.  Flags: cell 1 = 49 - x,
# cell 3 = 48 + x, cell 5 = 48, cell 15 = 49.  A mismatch lands one move past
# its flag, so cells 2, 4, 10 and 20 stay zero.
_SETUP = (
    "aaaaaal" + "s" + "f" + "a" * 8 + "ff" + "a" * 8 + "ffd" + "a" * 8
    + "dd" + "a" * 8 + "dd" + "l" + "fa" + "ffff" + "ddd" + "a" + "ddff"
)  # fmt: skip
# Pair -> (test and step to its flag, home after a mismatch, flag from home).
# ``j`` skips the first move on a zero index, so a match is one move nearer.
_FLAGS = {
    "10": ("jff", "fff", "f"),
    "01": ("jffff", "f", "fff"),
    "00": ("jdd", "ddd", "d"),
    "11": ("jdddd", "d", "ddd"),
}


def home_row(truth_table: str) -> str:
    """Return the shorter template: the table, or its reverse negated."""
    return min(
        _program(truth_table), _program(truth_table[::-1], negated=True), key=len
    )


def _program(truth_table: str, *, negated: bool = False) -> str:
    """Build a lookup (``negated``: weights on ``s``, cell -1) or a literal."""
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        # On zero, s/a decrements then restores; j/a skips the increment.
        # Every setter thus leaves the scratch cell zero, without an index gate.
        return (
            _CONSTANT_SETUP
            + (TEMPLATE_CHAR + "a") * n
            + "f"
            + "a" * int(truth_table[0])
            + "k"
        )
    # The leaf chain is up to 2**(n-1) leaves, so dropping an ignored input
    # halves the program; its gate stays with weight zero, so nothing moves
    # and no setter changes width.
    used = essential_inputs(truth_table, n)
    # A constant table depends on nothing and reduces to a one-input table,
    # never to the length-1 table, which is not a valid shape.
    table = truth_table if len(used) == n else read_at(truth_table, used or [0], n)
    # The last essential input is no weight: it moves the flags, so a leaf
    # covers a pair of rows and prints one of 0, 1, x, not x.
    last = used[-1] if used else None
    weights = {i: 2 ** (len(used) - 2 - slot) for slot, i in enumerate(used[:-1])}

    lead = "a" + TEMPLATE_CHAR + ("sla" if negated else "ls")
    gates = "".join(
        lead
        + ("fafffsf" if i == last else "fff" + "a" * weights.get(i, 0) + "ff")
        + "l"
        for i in range(n)
    )
    pairs = [table[i : i + 2] for i in range(0, len(table), 2)]
    runs = [(pair, len(list(group))) for pair, group in groupby(pairs)]
    # A run of equal pairs is one leaf behind ``js`` clamped decrements: ``j``
    # skips the ``s`` on a zero cell, so the index reaches the leaf as
    # ``max(index - (k - 1), 0)`` and the leaf's test lands on the run's pairs.
    # The last run needs no leaf, and nothing after the last guard reads the
    # index: that leaf need not decrement.
    leaves = [
        "js" * (length - 1)
        + _FLAGS[pair][0]
        + "lk;l"
        + _FLAGS[pair][1]
        + "s" * (at < len(runs) - 1)
        for at, (pair, length) in enumerate(runs[:-1], 1)
    ]
    return _SETUP + gates + "fff" + "".join(leaves) + _FLAGS[runs[-1][0]][2] + "k"


LANGUAGE = Language(
    "Home Row",
    "home_row",
    category="tape_based",
    boolean=home_row,
    # A sum, not a tree: a lookup over the essential inputs only.
    shape=Shape.REDUCING,
    contract=BooleanContract(),
    proof_workspace=(workspace, True, (2, 3, 4, 5, 6)),
    wrap=wrap_chars,
    example=Example(pair=HOME_ROW_PAIR),
)
