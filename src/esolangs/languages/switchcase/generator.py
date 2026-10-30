"""SwitchCase Boolean program generator: one switch over a row index.

Each input is read into ``x`` as ``'0'`` or ``'1'``; an essential one then
doubles the row index by a loop that moves it two at a time into the other
of ``A``/``B``, and a loop moves ``x - 48`` after it.  The index then meets
one switch with an arm ``k?'2`` for each row of the table's minority bit and
a default that prints the majority bit; case 2, jumped over at the start,
prints the minority bit and jumps to a last no-op case, so nothing runs
after an answer.  The loops' jump targets come before the switch, so they
cost O(log n) digits each.  A symmetric table skips the doubling and
switches over m + 1 rows ([ablations.symmetric_count]).

Size:
    O(T): 4.42 chars a row at n=16, plus O(n log n) for the loops; n=4
    parity: 238 chars, n=10 random 1847: 4,384 chars.

Decisions:
    One switch, not a block a hundred rows: a default would fire on the
    rows of the blocks after it.  An arm for the minority bit only is 4.42
    chars a row at n=16 against 7.06 for an arm every row in blocks, though
    the digits of k grow with n.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
    symmetric_weights,
)
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape


def switchcase(truth_table: str) -> str:
    """Build a SwitchCase program printing ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    symmetric = symmetric_weights(truth_table, n)
    if symmetric is not None:
        # A symmetric table adds its bits into one index over m + 1 rows,
        # never longer than the doubling build ([ablations.symmetric_count]).
        return _program(n, essential, symmetric[1], doubling=False)
    return _program(n, essential, table, doubling=True)


def _program(n: int, essential: list[int], table: str, *, doubling: bool) -> str:
    """Return the reads, the index loops and the switch over ``table``."""
    kept = set(essential)
    # Case 2 prints the minority bit; case 1 jumps over it to the reads.
    cases = ["$_\n0?=A=B=x'3", ""]
    doubled = 0
    for i in range(n):
        cases.append("$x\n0?,\n!,")
        if i not in kept:
            continue
        cur, nxt = ("A", "B") if doubled % 2 == 0 else ("B", "A")
        if doubling:
            doubled += 1
            # Cases are numbered from 1: the next one appended is len + 1.
            double = len(cases) + 1
            cases += [
                f"${cur}\n0?'{double + 3}\n!-1",
                f"${nxt}\n0?+2\n!+2",
                f"$_\n0?'{double}",
            ]
        else:
            nxt = cur
        carry = len(cases) + 1
        cases += [f"$x\n48?'{carry + 3}\n!-1", f"${nxt}\n0?+1\n!+1", f"$_\n0?'{carry}"]
    index = "B" if doubled % 2 else "A"
    major = "1" if 2 * table.count("1") > len(table) else "0"
    minor = "0" if major == "1" else "1"
    # A case needs an arm: -1 never matches, for the table with no minority row.
    rows = [k for k, bit in enumerate(table) if bit == minor] or [-1]
    # The unreachable -1 arm keeps case 2 legal (a case needs an arm).
    cases[1] = f"${index}\n-1?+0\n!={index}+{minor}@'{len(cases) + 2}"
    arms = "\n".join(f"{k}?'2" for k in rows)
    cases += [f"${index}\n{arms}\n!={index}+{major}@", "$_\n1?+0"]
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
