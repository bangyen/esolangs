"""Home Row Boolean program generator: a weighted index counted down a leaf chain.

Each input adds its binary weight to an index cell; guarded leaves count it
down onto a zero cell, printing at the selected row and skipping the rest.
Setters clear or preserve a fresh one; position-stable l/s/l gates add binary
weights without nested loops.  Ignored inputs keep a zero-weight gate; a
constant table discards all setters and prints a literal.  No goto, and ``l``
re-runs only its own block: no leaf of the linear chain is reached twice.

Size:
    Up to 2**n leaves in a linear chain; n=10 and: 1,175 chars (was 3,209),
    n=10 random 1847: 8,711 chars, n=10 parity: 10,359 chars.

Decisions:
    A negated twin takes a table when shorter: ``and`` at n=8 885 -> 385.
    Sharing runs of equal rows through ``js`` clamped decrements saves, at n=7,
    56.48% on random, 54.66% on tiled, 120.15% with one half constant and
    29.67% with constant blocks (deletion costs, 200 tables a class).
"""

from itertools import accumulate, groupby

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
_SETUP = "aaaaaalsffaaaaaaaaffflf"


def _runs(rows: str) -> list[tuple[int, str]]:
    """Return ``(end, run)`` for each maximal run of equal characters in ``rows``."""
    runs = ["".join(group) for _, group in groupby(rows)]
    return list(zip(accumulate(map(len, runs)), runs, strict=True))


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
            _SETUP + (TEMPLATE_CHAR + "a") * n + "f" + "a" * int(truth_table[0]) + "k"
        )
    # The leaf chain is up to 2**n leaves, so dropping an ignored input
    # halves the program; its gate stays with weight zero, so nothing moves
    # and no setter changes width.
    used = essential_inputs(truth_table, n)
    # A constant table depends on nothing and reduces to a one-input table,
    # never to the length-1 table, which is not a valid shape.
    table = truth_table if len(used) == n else read_at(truth_table, used or [0], n)
    weights = {i: 2 ** (len(used) - 1 - slot) for slot, i in enumerate(used)}

    head = "a" + TEMPLATE_CHAR + ("slaffff" if negated else "lsffff")
    bit_lines = [head + "a" * weights.get(i, 0) + "fl" for i in range(n)]
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
    return _SETUP + "".join(bit_lines) + "ffff" * bool(guarded) + "".join(leaves) + last


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
