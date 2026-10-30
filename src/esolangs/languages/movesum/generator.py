"""Movesum Boolean program generator: Horner read, then one rung per row.

Movesum has no conditional, but the halt rule is one: ``move A B`` leaves
the array unchanged iff cell A equals cell B, and the run ends at the first
two such commands in a row.  Each input is read by ``V := 2V + x`` through
``sum`` over cells 1-4, starting from V = 44, so V ends as 44T + v for the
row v.  The program then walks the rows in order: a rung is ``sum`` (the
counter, 44T + r), a test that is a no-op iff V equals the counter, and a
print of the row's answer.  At r = v the test and the print are two no-ops
in a row, so the run halts after printing table[v], the last number out.
Any other rung's test changes the array, so the walk goes on.

Size:
    Theta(T): 6 commands a row plus 6 an input; n=4 parity: 1,064 chars

Decisions:
    The offset 44 keeps every first-line value off 42, which the page
    replaces with an input.  Filler ticks between commands were not needed:
    every table to n=3 and random ones to n=8 ran without them.
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.registry._language import Example, Language, Shape

#: Cells: 0 sum, 1/2/3/4 addends (4 stays 0), 5 V, 6 test scratch, 7 garbage,
#: 8 one, 9 counter seed, 10 the input.
_OFFSET = 44


def movesum(truth_table: str) -> str:
    """Build a Movesum program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    seed = _OFFSET * len(truth_table) - 1
    lines = [f"1={seed} 2=1 5={_OFFSET} 7=3 8=1 9={seed}"]
    for _ in range(n):
        lines += ["move -1 10", "move 5 1", "move 5 3", "move 10 2", "sum", "move 0 5"]
    lines += ["move 9 1", "move 8 2", "move 4 3"]
    for bit in truth_table:
        lines += ["sum", "move 0 1", "move 7 6", "move 1 6", "move 5 6"]
        lines.append("move 2 -1" if bit == "1" else "move 4 -1")
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
