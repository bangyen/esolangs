"""Caballo Boolean program generator: the wiki's conditional as a tree.

The inputs are the stack, the first on top.  A node tests the top with
``(dip R1+(1+di-)p R0)``: ``d`` drops the stack on a 0 bit, emptying the
first branch, and the zero test ``(1+di-)`` cancels to nothing on a 1.
Both branches pop the bit.  A node whose halves agree pops it untested; a
constant subtable pops the rest and leaves ``[1]`` (``i``) or ``[]``, so
one stack survives at weight 1 and the output is never drawn at random.

Size:
    T-1 nodes at most, appended into one buffer: size and build time O(T);
    n=10 and: 171 chars, n=10 random 1847: 7,663 chars.

Decisions:
    Repeated subtrees are not shared: Caballo has no names or jumps, so code
    runs once per place it is written.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language


def caballo(truth_table: str) -> str:
    """Build a Caballo program printing ``[1]`` or ``[]`` for each row."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    out: list[str] = []

    def node(depth: int, k: int) -> None:
        if ids[depth][k] < 2:
            # The pops empty the stack, where ``q`` would be a round
            # trip (push a zero, the strip eats it), so ``i`` alone
            # leaves [1]; the leaf costs one ``p`` per remaining level
            # plus the answer char.
            out.append("p" * (n - depth) + ("i" if ids[depth][k] else ""))
            return
        zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
        if zero == one:
            out.append("p")
            node(depth + 1, 2 * k)
            return
        # The root keeps its conditional: an empty program is no program.
        if depth == n - 1 and depth:
            # The last bit is the stack: [1] already answers 1 and a 0
            # strips to [].  The complement drops a 1 bit's stack and
            # turns a 0 into [1] ([ablations.last_level_forms]).
            out.append("" if (zero, one) == (0, 1) else "(d+(1+di-)i)")
            return
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
