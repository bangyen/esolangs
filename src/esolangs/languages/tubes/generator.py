"""Tubes Boolean program generator: the table in memory, indexed by pointer moves.

Row 0 writes the lookup table right to left into memory row 0, a ``◉`` per
1 entry and a ``═`` (memory pointer one cell right) between entries, so the
pointer ends on entry 0.  ``╖`` drops the pointer to memory row 1, and row 1
runs left through one gadget per input: ``◇`` reads the bit, ``┬`` sends a
1 straight along ``w`` ``═`` cells (pointer ``w`` cells left, onto a fresh
0 cell) and a 0 down around a plain detour, and ``◉`` on both arms makes
the cell 1, which takes the merging ``┬`` left.  A weight-0 input is a bare
``◇``.  ``╚`` lifts the pointer onto the indexed entry, ``◆`` prints it.

The weights are the essential inputs' binary place values, or 1 each with
the table by popcount for a symmetric table, whichever draws shorter.

Size:
    about 3 cells per lookup entry and 5 per input: O(T) characters;
    n=4 parity: 75 chars, n=10 random 1847: 4,611 chars
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.projection import (
    WeightedLookup,
    input_weights,
    symmetric_lookup,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def _draw(lookup: WeightedLookup) -> str:
    """Draw ``lookup``; rows 1 and 2 are listed right to left."""
    top = "▶" + "═".join("◉" * (bit == "1") for bit in reversed(lookup.table)) + "╖"
    mid, low = ["┘"], [" "]
    for weight in lookup.weights:
        if weight:
            mid += ["◇", "┬", "═" * weight, "◉", "┬"]
            low += [" ", "┘", "─" * weight, "◉", "└"]
        else:
            mid.append("◇")
            low.append(" ")
    mid.append("┌┐◆▷")
    low.append("┘╚")
    right, left = "".join(mid)[::-1], "".join(low)[::-1]
    # Row 1 ends under the ``╖``; pad whichever side starts left of the other.
    shift = len(top) - len(right)
    pad = " " * max(0, shift)
    return "\n".join(
        (
            " " * max(0, -shift) + top,
            pad + right,
            (pad + left.rjust(len(right))).rstrip(),
        )
    )


def tubes(truth_table: str) -> str:
    """Build a Tubes program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    projected = input_weights(truth_table, n)
    candidates = [projected]
    symmetric = symmetric_lookup(projected)
    if symmetric is not None:
        candidates.append(symmetric)
    return min(map(_draw, candidates), key=len)


def tubes_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return tubes(request.table)
