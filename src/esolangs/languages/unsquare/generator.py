"""Unsquare Boolean program generator: a stack lookup popped by input weight.

Entries are pushed reversed as ``O``/``I`` so row ``r`` sits at depth ``r``;
each input read pops its bit's weight, leaving the addressed entry on top.
Runs of equal cells use a counted loop when shorter.  The first ``d``
essential inputs branch instead of popping (``_depth``): each pushes only its
half, so those reads' ``2**k`` pops leave the program.

Size:
    About 1.1 bytes per row, O(T), against 32.5 for a decision tree; n=10
    and: 454 chars, n=10 random 1847: 1,360 chars.

Decisions:
    Run loops: no saving on seeded random tables at n=6/7 (runs fall short
    of the ~9-entry break-even); the saving lives on run-rich tables
    ([ablations.run_loops]).
    Branching reads: ``(m - 3) // 2`` levels ([ablations.branch_reads]).
"""

from itertools import groupby

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def _run(entry: str, count: int) -> str:
    """Push ``count`` copies of ``entry`` (``O``/``I``), by a loop when shorter.

    The accumulator is set to ``2 * (count // 2)`` by Horner's rule (``x``
    doubles, ``+`` adds two); each trip runs ``>``, pushes two, subtracts two
    and runs ``<``.
    """
    bits = bin(count // 2)[2:]
    setup = "OA+" + "".join("x" + "+" * (bit == "1") for bit in bits[1:])
    loop = setup + ">" + entry * 2 + "-<" + entry * (count % 2)
    return entry * count if count <= len(loop) else loop


def _runs(bits: str) -> str:
    """Return the run-counted pushes."""
    return "".join(
        _run("I" if entry == "1" else "O", len(list(run)))
        for entry, run in groupby(bits)
    )


def _depth(m: int) -> int:
    """Branch levels for ``m`` essential inputs: ``(m - 3) // 2``, at least 0.

    Level ``d + 1`` swaps one read's ``2**(m-d-1)`` pops for ``2**d`` nodes of
    16 chars, paying while ``2**(m-d-1) + 10 > 16 * 2**d``; that holds up to
    ``(m - 3) // 2`` levels from m=5 (m=4 gains 2%).
    """
    return max(0, (m - 3) // 2)


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program for a binary ``2**n``-entry table, MSB first.

    Index ``2**m - 1`` against ``2**m`` cells prevents underflow.  A constant
    half costs about log of its length (:func:`_run`).
    """
    n = _validate_truth_table(truth_table)
    weights, reduced = input_weights(truth_table, n)
    m = len(reduced).bit_length() - 1
    depth = _depth(m)
    ess = [i for i in range(n) if weights[i]]

    def node(rows: str, k: int, left: int) -> str:
        """Read inputs from ``k``; branch on the next ``left`` essential ones."""
        if left == 0:
            return _runs(rows[::-1])
        if not weights[k]:
            return "iA" + node(rows, k + 1, left)
        half = len(rows) // 2
        # ``IA`` marks the taken branch so ``x->`` skips the else part.
        return (
            "iA>-<x>"
            + node(rows[half:], k + 1, left - 1)
            + "IA<x->"
            + node(rows[:half], k + 1, left - 1)
            + "OA<"
        )

    out = node(reduced, 0, depth)
    first = (ess[depth - 1] + 1) if depth else 0
    for weight in weights[first:]:
        if weight:
            out += "iA>-<x>" + "A" * weight + "OA<"
        else:
            out += "iA"
    return out + "A" + "+" * (_ASCII_ZERO // 2) + "Po"


LANGUAGE = Language(
    "Unsquare",
    "unsquare",
    category="stack_based",
    boolean=unsquare,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
