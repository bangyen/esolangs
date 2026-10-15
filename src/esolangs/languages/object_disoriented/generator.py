"""Object disoriented Boolean program generator: a tree of conditional calls.

``main`` first prints ``0011000``, the answer byte's fixed bits; output is
buffered until the 8th, so nothing is printed before the inputs are read.
An input byte is ``0011000x``, MSB first: a node drops seven bits and keeps
the eighth in ``t`` (``iiiiiiicit``).  ``f t X`` runs ``X`` only on a 1, and
``N`` (``fpz cbs``) acts as a 1 until a 1 bit calls it and ``s`` becomes
``z``, so ``clN.afta`` leaves the negation in ``a`` and ``fan X0`` runs
``X0`` only on a 0.  Each branch is an object ``n ... rz zz``, so its ``t``
and ``a`` are its own.  A node whose halves agree drops its bit untested; a
constant subtable drops the rest and prints the last bit (``lI.``, the
input's own 1, or ``z``).

Size:
    T-1 nodes at most: size and build time O(T); n=8 parity: 9,748 chars,
    n=10 majority: 20,174 chars, n=10 and: 789 chars.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: ``I`` is the bit 1; ``N`` is 1 until a 1 bit calls it.
_HEADER = "dI.fpzrzzz dN.fpzcbsrzzz dmain.ozozolI.olI.ozozoz "


def object_disoriented(truth_table: str) -> str:
    """Build an Object disoriented program printing ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    out = [_HEADER]

    def node(depth: int, k: int) -> None:
        if ids[depth][k] < 2:
            out.append("i" * 8 * (n - depth) + ("olI." if ids[depth][k] else "oz"))
            return
        zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
        if zero == one:
            out.append("iiiiiiii")
            node(depth + 1, 2 * k)
            return
        out.append(" iiiiiiicitclN.afta ftn")
        node(depth + 1, 2 * k + 1)
        out.append("rzzz fan")
        node(depth + 1, 2 * k)
        out.append("rzzz")

    node(0, 0)
    out.append(" rzzz")
    return "".join(out)


LANGUAGE = Language(
    "Object disoriented",
    "object_disoriented",
    category="other",
    boolean=object_disoriented,
    contract=BooleanContract(
        input_shape="char_stream",
        note="Object disoriented reads input bits most significant first, so "
        "a program keeps each input byte's eighth bit and drops the seven before it",
    ),
    # Whitespace is ignored everywhere, class names included.
    wrap=wrap_chars,
    empty_program="Object disoriented program defines no 'main' class",
)
