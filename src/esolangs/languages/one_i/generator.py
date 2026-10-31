"""1 + i Boolean program generator: a decision tree of function literals.

A node pushes its 0- and 1-child as function literals, reads its bit with
``B`` and lets ``?`` invoke one.  ``?`` leaves both literals on the stack, and
nothing ever returns to them, so they are left there.  A node whose halves
agree (``subtree_ids``) reads its bit and drops it: ``B$`` then the child.  A
constant subtable prints ``iic+`` (0) or ``ici*`` (1) first, then reads its
bits with bare ``B``; a last-level node prints ``b`` or ``1 - b`` (``b > 0``),
and a node of two constants prints that and drains the last bit.

Size:
    O(T), at most 4n + 3 steps; n=10 and: 146 chars, n=10 random 1847: 4,565 chars.

Decisions:
    Other repeats are not shared: a deeper function needs a whole-stack roll.
    A constant prints before draining: after ``p`` nothing reads the stack,
    so bare ``B`` replaces ``B$`` (2n+5 -> n+5 a table).  Leaving the literals
    makes the stack grow two a level (workspace, not size).
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.one_i.proof_formulas import workspace
from esolangs.registry._language import Language

_CONSTANT = ("iic+", "ici*")


def one_i(truth_table: str) -> str:
    """Build a 1 + i program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)

    def node(depth: int, k: int) -> str:
        sub = ids[depth][k]
        if sub < 2:
            return _CONSTANT[sub] + "p" + "B" * (n - depth)
        zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
        if depth == n - 1:
            return "Bp" if (zero, one) == (0, 1) else "Biic+>p"
        if depth == n - 2 and zero < 2 and one < 2:
            # Constant pairs ignore the last input: b or 1 - b, then drain it.
            return ("Bp" if zero == 0 else "Biic+>p") + "B"
        if zero == one:
            return "B$" + node(depth + 1, 2 * k)
        return f"[{node(depth + 1, 2 * k)}][{node(depth + 1, 2 * k + 1)}]B?"

    return node(0, 0)


LANGUAGE = Language(
    "1 + i",
    "one_i",
    category="stack_based",
    boolean=one_i,
    wrap=wrap_chars,
    proof_workspace=(workspace, True, (2, 3, 4, 5, 6, 7, 8, 9)),
)
