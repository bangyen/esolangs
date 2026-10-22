"""Stisp Boolean program generator: a decision diagram walked by frames.

The head is the current node, an atom named by its subtable id; each input
is one frame ``->s[b]`` below it, first input on top.  A node has an
equation per bit, ``N->s[0]=L;`` and ``N->s[1]=H;``, and the frame's rewrite
replaces the node with the child; a node whose halves agree has one
equation over a variable.  The leaves are the atoms ``0`` and ``1``, and the
last equation, ``c->s[x]=c;``, drains the frames under a leaf, so the result
is the answer.  For AND:

    3->s[0]=0;3->s[1]=2;2->s[0]=0;2->s[1]=1;c->s[x]=c;3->s[$]->s[$]

Size:
    O(T) text: one or two equations a node of the reduced diagram;
    n=4 parity: 175 chars, n=10 random 1847: 5,884 chars.

Decisions:
    Ids repeat only within a level (:func:`subtree_ids`), so equal subtables
    share a node.
"""

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    subtree_ids,
)
from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.stisp.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

#: Each input is one atom, ``0`` or ``1``, inside its frame.
PAIR = ("0", "1")
#: The drain: under a leaf every remaining frame rewrites to the leaf.
_DRAIN = "c->s[x]=c;"
#: A newline is whitespace, legal anywhere but inside an identifier or ``->``.
_TOKEN = r"->|[A-Za-z0-9_]+|[\s\S]"


def stisp(truth_table: str) -> str:
    """Build a Stisp template whose result is ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    equations: list[str] = []
    for level in range(n):
        seen = set()
        for k, node in enumerate(ids[level]):
            if node < 2 or node in seen:
                continue
            seen.add(node)
            lo, hi = ids[level + 1][2 * k], ids[level + 1][2 * k + 1]
            if lo == hi:
                equations.append(f"{node}->s[x]={lo};")
            else:
                equations.append(f"{node}->s[0]={lo};{node}->s[1]={hi};")
    frames = f"->s[{TEMPLATE_CHAR}]" * n
    return "".join(equations) + _DRAIN + f"{ids[0][0]}{frames}"


LANGUAGE = Language(
    "Stisp",
    "stisp",
    category="other",
    boolean=stisp,
    contract=BooleanContract(
        answer_mode="dump",
        note="Stisp has no input or output: each input is the atom 0 or 1 "
        "in its frame, and the result, printed at halt, is the answer atom",
    ),
    wrap=TokenWrapper(_TOKEN),
    empty_program="a Stisp program needs a stack expression",
    example=Example(pair=PAIR),
    proof_workspace=(workspace, True, (3, 4, 5, 6, 7)),
)
