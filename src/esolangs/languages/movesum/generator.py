"""Movesum Boolean program generator: Horner read, then one rung per row.

Movesum has no conditional, but the halt rule is one: ``move A B`` leaves
the array unchanged iff cell A equals cell B, and the run ends at the first
two such commands in a row.  Each input is read by ``V := 2V + x`` through
``sum`` over cells 1-4, starting from V = 44, so V ends as 44T + v for the
row v.  The program then walks the rows in order: a rung is a print of the
row's answer, ``sum`` (the counter, 44T + r) and ``move 0 1``, then
``move 1 6`` and ``move 5 6``.  Cell 6 holds V after every rung that did not
halt (and 44T before the first), so ``move 1 6`` is a no-op iff V equals the
counter and ``move 5 6`` then is too: at r = v the run halts right after
printing table[v], the last number out.  Any other rung changes cell 6
twice, so the walk goes on.

Size:
    Theta(T): 5 commands a row plus 6 an input; n=4 parity: 922 chars

Decisions:
    The offset 44 keeps every first-line value off 42, which the page
    replaces with an input.  Filler ticks between commands were not needed:
    every table to n=3 and random ones to n=8 ran without them.  Printing
    before the test, not after, drops the scratch load ``move 7 6`` that
    forced cell 6 off the counter: 6 -> 5 commands a rung
    ([ablations.print_before_test]).
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.registry._language import Example, Language, Shape

#: Cells: 0 sum, 1/2/3/4 addends (4 stays 0), 5 V, 6 test cell (holds V between rungs),
#: 8 one, 9 counter seed, 10 the input.
_OFFSET = 44


def movesum(truth_table: str) -> str:
    """Build a Movesum program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    seed = _OFFSET * len(truth_table) - 1
    lines = [f"1={seed} 2=1 5={_OFFSET} 6={seed + 1} 8=1 9={seed}"]
    for _ in range(n):
        lines += ["move -1 10", "move 5 1", "move 5 3", "move 10 2", "sum", "move 0 5"]
    lines += ["move 9 1", "move 8 2", "move 4 3"]
    for bit in truth_table:
        lines.append("move 2 -1" if bit == "1" else "move 4 -1")
        lines += ["sum", "move 0 1", "move 1 6", "move 5 6"]
    return "\n".join(lines) + "\n"


LANGUAGE = Language(
    "Movesum",
    "movesum",
    category="tape_based",
    boolean=movesum,
    # Not a tree: one rung per row, whatever the table says.
    shape=Shape.LOOKUP,
    eof="a read at EOF is 0",
    empty_program="Movesum program is empty",
    example=Example(expected="0 0"),
    no_wrap="each line is one instruction and a break splits it",
)
