"""Rubic Boolean program generator: a cube-neutral decision tree.

The opening ``r' d'`` leaves the cube in a state X.  A node stores its bit
with ``r2``, its own inverse, and every subtree leaves the cube as it found
it, so the cube is X or Y = X·r2: Y exactly when the node's own store was
taken.  A node whose halves differ:

    .wo -ow ( ! ) %og       V = -1, so the loop reads backwards: V = 48+b; -> b
    ( r2 )                  store b: the cube is Y iff b
    Q ( T0 )                Q = 1 on X, 0 on Y: the 0 half, run on X
    P ( r2 T1 )             P = 0 on X, 1 on Y: undo the store, run the 1 half

The undo sits inside the 1 branch, so no branch tests or undoes after it
and every subtree runs on X.  With P = ``.wg`` and Q = ``.wg' -gw``.  A node
whose halves agree reads its bit and goes on; a constant subtable reads the
rest and prints with ``.ww +ww *ww -og !`` (48) or ``-ow`` (49).  Every
expression is in :data:`_TABLE`, whose values on X and Y the tests check, so
by induction each evaluates as stated wherever the program reaches it.

Size:
    At most T-1 nodes of bounded tokens: O(T) size and build; n=10 parity:
    68,564 chars, n=10 random 1847: 48,096 chars, n=10 and: 1,323 chars.

Decisions:
    Repeated subtrees are not shared: Rubic has no jump or call, so code runs
    once per place it is written.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

_OPENING: tuple[str, ...] = ("r'", "d'")
_TABLE: dict[str, tuple[str, ...]] = {
    "read": (".wo", "-ow", "(", "!", ")"),
    "bit": ("%og",),
    "print0": (".ww", "+ww", "*ww", "-og", "!"),
    "print1": (".ww", "+ww", "*ww", "-ow", "!"),
    "P": (".wg",),
    "Q": (".wg'", "-gw"),
}


def rubic(truth_table: str) -> str:
    """Build a Rubic program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    out: list[str] = list(_OPENING)

    def node(depth: int, k: int) -> None:
        if ids[depth][k] < 2:
            out.extend(_TABLE["read"] * (n - depth))
            out.extend(_TABLE["print1" if ids[depth][k] else "print0"])
            return
        out.extend(_TABLE["read"])
        if ids[depth + 1][2 * k] == ids[depth + 1][2 * k + 1]:
            node(depth + 1, 2 * k)
            return
        out.extend((*_TABLE["bit"], "(", "r2", ")", *_TABLE["Q"], "("))
        node(depth + 1, 2 * k)
        out.extend((")", *_TABLE["P"], "(", "r2"))
        node(depth + 1, 2 * k + 1)
        out.append(")")

    node(0, 0)
    return " ".join(out)


LANGUAGE = Language(
    "Rubic",
    "rubic",
    category="register_based",
    boolean=rubic,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=wrap_space_delimited,
)
