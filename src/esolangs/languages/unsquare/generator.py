"""Unsquare Boolean program generator: a stack lookup popped by input weight.

Entries are pushed reversed as ``O``/``I`` so row ``r`` sits at depth ``r``;
each input read pops its bit's weight, leaving the addressed entry on top.
Runs of equal cells use a counted loop when shorter.

Size:
    Two bytes per row, O(T), against 32.5 for a decision tree; n=10 and:
    1,176 chars, n=10 random 1847: 2,174 chars.

Decisions:
    Run loops: no saving on seeded random tables at n=6/7 (runs fall short
    of the ~9-entry break-even); the saving lives on run-rich tables
    ([ablations.run_loops]).
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


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program for a binary ``2**n``-entry table, MSB first.

    Index ``2**m - 1`` against ``2**m`` cells prevents underflow.  A constant
    half costs about log of its length (:func:`_run`).
    """
    n = _validate_truth_table(truth_table)
    weights, reduced = input_weights(truth_table, n)
    bits = reduced[::-1]
    cells = _runs(bits)
    blocks: list[str] = []
    for weight in weights:
        if weight:
            # ``>-<`` subtracts 2 to reach the input character's parity; ``x``
            # doubles it, ``>`` pops only for 1, ``OA`` zeroes it for the ``<``.
            blocks.append("iA>-<x>" + "A" * weight + "OA<")
        else:
            blocks.append("iA")  # consume the line, leave the stack alone
    return cells + "".join(blocks) + "A" + "+" * (_ASCII_ZERO // 2) + "Po"


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
