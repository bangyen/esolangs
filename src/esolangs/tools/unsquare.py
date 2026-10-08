"""Boolean program generator for Unsquare."""

from itertools import groupby

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)


def _run(entry: str, count: int) -> str:
    """Push ``count`` copies of ``entry`` (``O``/``I``), by a loop when shorter.

    The accumulator is set to ``2 * (count // 2)`` by Horner's rule (``x``
    doubles, ``+`` adds two); each trip pushes two and subtracts two.
    """
    bits = bin(count // 2)[2:]
    setup = "OA+" + "".join("x" + "+" * (bit == "1") for bit in bits[1:])
    loop = setup + ">" + entry * 2 + "-<" + entry * (count % 2)
    return min(entry * count, loop, key=len)


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program for a binary ``2**n``-entry table, MSB first.

    Reversed ``O``/``I`` entries put row ``r`` at depth ``r``; each read pops
    its bit's weight: two bytes per row, against 32.5 for a decision tree.
    ``>-<`` subtracts 2 to reach the input character's parity; ``x`` doubles
    it, ``>`` pops only for 1, ``OA`` zeroes it for the returning ``<``.
    Index ``2**m - 1`` against ``2**m`` cells prevents underflow.  A run of
    equal cells is pushed by a loop when shorter, so a constant half costs
    about log of its length (:func:`_run`; -15% at n=7, -10% at n=6, 12 seeded
    tables).  A repeated block is not shared: a loop counts in the accumulator,
    which every pop overwrites, so only a run of one cell can be counted.
    """
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    reduced = read_at(truth_table, used, n)
    cells = "".join(
        _run("I" if entry == "1" else "O", len(list(run)))
        for entry, run in groupby(reversed(reduced))
    )
    blocks: list[str] = []
    for index in range(n):
        if index in used:
            weight = 1 << (len(used) - 1 - used.index(index))
            blocks.append("iA>-<x>" + "A" * weight + "OA<")
        else:
            blocks.append("iA")  # consume the line, leave the stack alone
    return cells + "".join(blocks) + "A" + "+" * (_ASCII_ZERO // 2) + "Po"


LANGUAGE = Language(
    "Unsquare",
    "stack_based.unsquare",
    boolean=unsquare,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
