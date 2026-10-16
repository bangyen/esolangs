"""1 + i Boolean program generator: a decision tree of function literals.

A node pushes its 0- and 1-child as function literals, reads its bit with
``B`` and lets ``?`` invoke one; ``?`` leaves both on the stack, so every child
starts with ``$$``.  Equal halves (``subtree_ids``) push one literal and ``:``
it.  A constant subtable still reads its bits (``B$`` each) and prints
``iic+`` (0) or ``ici*`` (1); a last-level 0/1 node prints ``b`` or ``1 - b``
(``ici*Bii**+``).

Size:
    O(T) size and build, at most 6n + 5 steps; n=10 and: 227 chars,
    n=10 random 1847: 7,527 chars.

Decisions:
    Other repeats are not shared: a deeper function needs a whole-stack roll.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._language import Language

_CONSTANT = ("iic+", "ici*")


def one_i(truth_table: str) -> str:
    """Build a 1 + i program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)

    def node(depth: int, k: int) -> str:
        sub = ids[depth][k]
        if sub < 2:
            return "B$" * (n - depth) + _CONSTANT[sub] + "p"
        zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
        if depth == n - 1:
            return "Bp" if (zero, one) == (0, 1) else "ici*Bii**+p"
        if zero == one:
            return f"[$${node(depth + 1, 2 * k)}]:B?"
        return f"[$${node(depth + 1, 2 * k)}][$${node(depth + 1, 2 * k + 1)}]B?"

    return node(0, 0)


LANGUAGE = Language(
    "1 + i",
    "one_i",
    category="stack_based",
    boolean=one_i,
    # Whitespace is ignored, so a newline anywhere is harmless.
    wrap=wrap_chars,
)
