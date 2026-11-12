"""Movesum Boolean program generator: Horner read, then one rung per row.

Movesum has no conditional, but the halt rule is one: ``move A B`` leaves
the array unchanged iff cell A equals cell B, and the run ends at the first
two such commands in a row.  Each input is read by ``V := 2V + x`` through
``sum`` over cells 1-4, starting from V = 44, so V ends as 44T + v for the
row v. Each rung sums the next counter, copies it to cell 1, prints the
answer, then copies V into cell 0. The print is one no-op; the copy is a
second exactly when counter = V, halting at table[v]. A mismatch clobbers
cell 0, but the next sum recomputes it from addends 1-4. That sum may be
one no-op; copying its increasing counter to cell 1 always resets the pair.

Size:
    O(T): 4 commands a row plus 6 an input; n=4 parity: 772 chars.
    Constants use 2n + 3 commands; n=8 zero: 179 chars.

Decisions:
    The offset 44 keeps every first-line value off 42, which the page
    replaces with an input.  Filler ticks between commands were not needed:
    every table to n=3 and random ones to n=8 ran without them.  Printing
    before the comparison lets the sum slot double as its test cell:
    cell 1 preserves the counter while cell 0 is overwritten with V.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program

#: Cells: 0 sum/test, 1/2/3/4 addends (4 stays 0), 5 V,
#: 8 one, 9 counter seed, 10 the input.
_OFFSET = 44


def movesum(truth_table: str) -> str:
    """Build a Movesum program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        # Reset to 2 between bit reads: two unchanged reads would halt early.
        return (
            f"1=2 2={truth_table[0]}\n"
            + "move -1 0\nmove 1 0\n" * n
            + "move 2 -1\nmove 0 0\n"
        )
    seed = _OFFSET * len(truth_table) - 1
    lines = [f"1={seed} 2=1 5={_OFFSET} 8=1 9={seed}"]
    for _ in range(n):
        lines += ["move -1 10", "move 5 1", "move 5 3", "move 10 2", "sum", "move 0 5"]
    lines += ["move 9 1", "move 8 2", "move 4 3"]
    for bit in truth_table:
        lines += ["sum", "move 0 1"]
        lines.append("move 2 -1" if bit == "1" else "move 4 -1")
        lines.append("move 5 0")
    return "\n".join(lines) + "\n"


def movesum_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return movesum(request.table)
