"""Caballo Boolean program generator: the wiki's conditional, as a signed sum.

The inputs are the stack, the first on top.  Selectors split the stack by the
top bit: ``di`` keeps a 1 (a 0 drops), ``(1+di-)`` keeps a 0 (the 1's ``-1``
cancels the ``1``), and ``p`` pops it.  A tree of them leaves one empty stack
of weight 1 per row where the table is 1 and no stack where it is 0, so a
0-subtable costs nothing and a node with one live child drops its sum:
``dip`` or ``(1+di-)p``, then the child.  The empty stack is turned into
the answer once, after the tree: ``(i+-)`` maps ``[]`` to ``[1]`` plus ``-[]``,
and a sibling branch of n pops adds the ``[]`` of weight 1, so a 1 row ends as
``[1]`` and a 0 row as ``[]``.  A table with more ones than zeros builds the
complement's tree and ends ``(1+i-)`` beside n pops and an ``i``
([ablations.signed_sum]).
A constant subtable pops what is left (``p`` per level); a node whose halves
agree pops its input untested.

Size:
    39T/4 + n - 6 chars at most (parity); n=10 and: 48 chars, n=10 random
    1847: 6,531 chars.

Decisions:
    Repeated subtrees are not shared: Caballo has no names or jumps, so code
    runs once per place it is written.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language


def caballo(truth_table: str) -> str:
    """Build a Caballo program printing ``[1]`` or ``[]`` for each row.

    A table with more ones than zeros builds the complement's tree
    ([ablations.signed_sum]).
    """
    n = _validate_truth_table(truth_table)
    if "1" not in truth_table:
        return "p" * n
    if "0" not in truth_table:
        return "p" * n + "i"
    if 2 * truth_table.count("1") > len(truth_table):
        flipped = "".join("10"[c == "1"] for c in truth_table)
        return f"({_tree(flipped, n)}(1+i-)+{'p' * n}i)"
    return f"({_tree(truth_table, n)}(i+-)+{'p' * n})"


def _tree(truth_table: str, n: int) -> str:
    """Selectors leaving an empty stack of weight 1 on each 1 row."""
    ids = subtree_ids(truth_table)
    out: list[str] = []

    def node(depth: int, k: int) -> None:
        if ids[depth][k] < 2:
            # Reached only as a live constant 1: a 0 child is never entered.
            out.append("p" * (n - depth))
            return
        zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
        if zero == one:
            out.append("p")
            node(depth + 1, 2 * k)
        elif zero == 0:
            out.append("dip")
            node(depth + 1, 2 * k + 1)
        elif one == 0:
            out.append("(1+di-)p")
            node(depth + 1, 2 * k)
        else:
            out.append("(dip")
            node(depth + 1, 2 * k + 1)
            out.append("+(1+di-)p")
            node(depth + 1, 2 * k)
            out.append(")")

    node(0, 0)
    return "".join(out)


LANGUAGE = Language(
    "Caballo",
    "caballo",
    category="stack_based",
    boolean=caballo,
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"^(\[\]|\[1\])$",
        answer_values=("[]", "[1]"),
        note="Caballo reads its inputs as the initial stack, the first on "
        "top, and prints the surviving stack: [1] for one, [] for zero",
    ),
    wrap=wrap_chars,
    random=True,
    eof="the whole input is read once as the initial stack; no read meets EOF",
    example=Example(expected="[]"),
)
