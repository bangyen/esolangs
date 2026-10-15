"""Rubic Boolean program generator: a cube-neutral decision tree.

The opening ``r' d'`` leaves the cube in a state X.  A node stores its bit
with ``r2``, its own inverse, and undoes it before it ends, so every
subtree leaves the cube as it found it and the cube is always X or
Y = X·r2: Y exactly when an odd number of stores are taken on the path.
A node whose halves differ, at parity j:

    .wo -ow ( ! ) %og       V = -1, so the loop reads backwards: V = 48+b; -> b
    ( r2 )                  store b: the parity flips iff b
    E1 ( T1 )               E1 = 1 on the flipped state, 0 on the other
    E0 ( T0 )               E0 = the reverse
    E1 ( r2 )               undo the store

With P = ``.wg`` (0 on X, 1 on Y) and Q = ``.wg' -gw`` (1 on X, 0 on Y),
E1, E0 = P, Q at j = 0 and Q, P at j = 1.  A node whose halves agree reads
its bit and goes on; a constant subtable reads the rest and prints with
``.ww +ww *ww -og !`` (48) or ``-ow`` (49).  Every expression is in
:data:`_TABLE`, whose values on X and Y the tests check, so by induction
each evaluates as stated wherever the program reaches it.

Size:
    At most T-1 nodes of bounded tokens: O(T) size and build; n=10 parity:
    79,303 chars, n=10 random 1847: 55,063 chars, n=10 and: 1,428 chars.

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

    def node(depth: int, k: int, parity: int) -> None:
        if ids[depth][k] < 2:
            out.extend(_TABLE["read"] * (n - depth))
            out.extend(_TABLE["print1" if ids[depth][k] else "print0"])
            return
        out.extend(_TABLE["read"])
        if ids[depth + 1][2 * k] == ids[depth + 1][2 * k + 1]:
            node(depth + 1, 2 * k, parity)
            return
        e1, e0 = (
            (_TABLE["P"], _TABLE["Q"]) if parity == 0 else (_TABLE["Q"], _TABLE["P"])
        )
        out.extend((*_TABLE["bit"], "(", "r2", ")", *e1, "("))
        node(depth + 1, 2 * k + 1, 1 - parity)
        out.extend((")", *e0, "("))
        node(depth + 1, 2 * k, parity)
        out.extend((")", *e1, "(", "r2", ")"))

    node(0, 0, 0)
    return " ".join(out)


LANGUAGE = Language(
    "Rubic",
    "rubic",
    category="register_based",
    boolean=rubic,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=wrap_space_delimited,
)
