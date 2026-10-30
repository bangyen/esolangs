"""Monotonic Boolean generator: a decision tree walked by pointer divergence.

No bit is ever cleared, so a branch cannot flip a flag.  The tree is laid out
along the tape instead: every node and leaf is entered on a zero cell whose
left neighbour is 1, and leaves the pointer on a zero cell to the right of
everything written.  A node reads its input bit ``x`` onto its entry cell
``p`` (the other seven bits of the byte are consumed at the 1 in ``p+1``,
which it sets), then runs ``[>>`` one ``>]>[>`` zero ``>]``.  On ``x=1`` the
first loop runs the one-subtree from ``p+2``, its ``]`` retests a zero cell
and exits, and the second ``[`` meets a zero cell and skips the zero-subtree.
On ``x=0`` the first loop is skipped and ``>`` lands on the 1 at ``p+1``, so
only the zero-subtree runs.  A leaf prints ``'0'``/``'1'`` (bits ``v 0 0 0 1
1 0 0``) reading the 1 on its left.  A constant span is a leaf and an input
whose halves are equal is consumed untested; both read the 1 on the entry
cell's left, ``<`` then eight ``,`` a byte then ``>``.

Size:
    Linear in T = 2^n: worst 34T - 21 chars (parity); n=4 parity: 523 chars
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Read onto ``p``, then consume the byte's other seven bits on a set bit.
_READ = ">1<,>,,,,,,,<"
_LEAF = {0: ";;;;<;;>;;", 1: "<;>;;;<;;>;;"}


def _consume(inputs: int) -> str:
    """Read ``inputs`` whole bytes on the set bit left of the entry cell."""
    return "<" + "," * (8 * inputs) + ">" if inputs else ""


def monotonic_boolfuck(truth_table: str) -> str:
    """Build a Monotonic Boolfuck program printing ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)

    def tree(depth: int, k: int, pending: int) -> str:
        """Code for subtable ``k`` at ``depth`` after ``pending`` untested inputs."""
        node = ids[depth][k]
        if node < 2:
            return _consume(pending + n - depth) + _LEAF[node]
        zero, one = 2 * k, 2 * k + 1
        if ids[depth + 1][zero] == ids[depth + 1][one]:
            return tree(depth + 1, zero, pending + 1)
        return (
            f"{_consume(pending)}{_READ}[>>{tree(depth + 1, one, 0)}>]"
            f">[>{tree(depth + 1, zero, 0)}>]"
        )

    return "1>" + tree(0, 0, 0)


LANGUAGE = Language(
    "Monotonic Boolfuck",
    "monotonic_boolfuck",
    category="tape_based",
    boolean=monotonic_boolfuck,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=wrap_chars,
    eof="EOF supplies zero bits",
)
