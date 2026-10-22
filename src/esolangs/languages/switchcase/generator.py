"""SwitchCase Boolean program generator: switch blocks over a row index.

Each input is read into ``x`` as ``'0'`` or ``'1'``; an essential one then
doubles the row index by a loop that moves it two at a time into the other
of ``A``/``B``, and a loop moves ``x - 48`` after it.  The index then meets a
block per hundred rows of the table read at the essential inputs: a switch whose
arm ``k?...`` turns index ``k`` into its row's bit, then

    $R
    0?@-2
    1?@-2
    !-100

which prints a bit and leaves the index negative for good, or takes a hundred
off it for the next block.  The loops' jump targets come before any block, so
they cost O(log n) digits each.

Size:
    O(T): 7.06 chars a row at n=16, plus O(n log n) for the loops; n=4
    parity: 440 chars, n=10 random 1847: 8,002 chars.

Decisions:
    A hundred rows a block, the most whose arm integers stay two digits:
    7.10 chars a row at n=14, against 7.37 for ten and 7.53 for 128.  A
    countdown of one zero-test a row was 14.0 chars a row and leaves the
    switch's arms unused.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

#: Rows a block's switch covers.
BLOCK = 100


def _blocks(table: str, index: str) -> list[str]:
    """Return the selection cases for ``table`` on the index variable."""
    cases = []
    for start in range(0, len(table), BLOCK):
        arms = []
        for k, bit in enumerate(table[start : start + BLOCK]):
            delta = int(bit) - k
            arms.append(f"{k}?{'-' if delta < 0 else '+'}{abs(delta)}")
        cases.append(f"${index}\n" + "\n".join(arms))
        cases.append(f"${index}\n0?@-2\n1?@-2\n!-{BLOCK}")
    return cases


def switchcase(truth_table: str) -> str:
    """Build a SwitchCase program printing ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    kept = set(essential)
    cases = ["$_\n0?=A=B=x"]
    doubled = 0
    for i in range(n):
        cases.append("$x\n0?,\n!,")
        if i not in kept:
            continue
        cur, nxt = ("A", "B") if doubled % 2 == 0 else ("B", "A")
        doubled += 1
        # Cases are numbered from 1: the next one appended is len + 1.
        double = len(cases) + 1
        cases += [
            f"${cur}\n0?'{double + 3}\n!-1",
            f"${nxt}\n0?+2\n!+2",
            f"$_\n0?'{double}",
        ]
        carry = len(cases) + 1
        cases += [f"$x\n48?'{carry + 3}\n!-1", f"${nxt}\n0?+1\n!+1", f"$_\n0?'{carry}"]
    index = "B" if doubled % 2 else "A"
    cases += _blocks(read_at(truth_table, essential, n), index)
    return "\n".join(cases) + "\n"


LANGUAGE = Language(
    "SwitchCase",
    "switchcase",
    category="variable_based",
    boolean=switchcase,
    # Not a tree: the table is one arm a row, picked by the row index.
    shape=Shape.LOOKUP,
    contract=BooleanContract(input_shape="char_stream"),
    no_wrap="a line is one arm, and a case's arms follow its $ line",
)
