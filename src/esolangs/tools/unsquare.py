"""Boolean program generator for Unsquare."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)


def unsquare(truth_table: str) -> str:
    """Build an Unsquare program for a binary ``2**n``-entry table, MSB first.

    Reversed ``O``/``I`` entries put row ``r`` at depth ``r``; each read pops
    its bit's weight: two bytes per row, against 32.5 for a decision tree.
    ``>-<`` subtracts 2 to reach the input character's parity; ``x`` doubles
    it, ``>`` pops only for 1, ``OA`` zeroes it for the returning ``<``.
    Index ``2**m - 1`` against ``2**m`` cells prevents underflow.
    """
    n = _validate_truth_table(truth_table)
    used = essential_inputs(truth_table, n) or [0]
    reduced = read_at(truth_table, used, n)
    cells = "".join("I" if entry == "1" else "O" for entry in reversed(reduced))
    blocks: list[str] = []
    for index in range(n):
        if index in used:
            weight = 1 << (len(used) - 1 - used.index(index))
            blocks.append("iA>-<x>" + "A" * weight + "OA<")
        else:
            blocks.append("iA")  # consume the line, leave the stack alone
    return cells + "".join(blocks) + "A" + "+" * (_ASCII_ZERO // 2) + "Po"
