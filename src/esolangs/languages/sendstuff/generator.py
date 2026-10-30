"""SendStuff Boolean program generator: a shared decision diagram.

Every distinct subtable is one named node, defined before the nodes that
send to it and reached from the last line, ``>root``.  A node is an
``Input``, which reads the next ``0`` (48) or ``1`` (49) whatever it
receives; ``Subtract 49`` passes only a 1, and ``Divide 48`` (48 // 48 is
1, 48 // 49 is 0) then ``Subtract 1`` only a 0, so each bit reaches one
child.  The macros ``!o`` and ``!z`` write the two branches.  A node whose
halves agree reads its bit and sends on; a constant subtable is a chain
reading the remaining inputs into ``Constant 48`` or ``49`` and Output.
Names are ``subtree_ids`` ids, the chains ``z<depth>``/``o<depth>``.

Size:
    O(T) size and build time: at most T - 1 diagram nodes and 2n chain nodes;
    n=10 parity: 485 chars, n=10 random 1847: 5,220 chars.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.sendstuff.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

_MACROS = "@o(>(Subtract 49>%))@z(>(Divide 48>(Subtract 1>%)))"


def sendstuff(truth_table: str) -> str:
    """Build a SendStuff program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)

    def name(depth: int, k: int) -> str:
        sub = ids[depth][k]
        return "zo"[sub] + str(depth) if sub < 2 else str(sub)

    # Reachable nodes, deepest first so every reference is already defined.
    levels: list[dict[str, str]] = [{} for _ in range(n + 1)]
    frontier = {0}
    for depth in range(n + 1):
        below: set[int] = set()
        for k in sorted(frontier):
            sub, here = ids[depth][k], name(depth, k)
            if here in levels[depth]:
                continue
            if depth == n:
                body = f"Constant {48 + sub}>(Output)"
            elif sub < 2 or ids[depth + 1][2 * k] == ids[depth + 1][2 * k + 1]:
                body = f"Input>{name(depth + 1, 2 * k)}"
                below.add(2 * k)
            else:
                body = (
                    f"Input!o {name(depth + 1, 2 * k + 1)} !z {name(depth + 1, 2 * k)}"
                )
                below |= {2 * k, 2 * k + 1}
            levels[depth][here] = f"|{here}({body})"
        frontier = below
    nodes = [node for level in reversed(levels) for node in level.values()]
    return "".join([_MACROS, *nodes, ">", name(0, 0)])


#: Break between words: a newline inside ``>17``, ``>%`` or ``!o`` splits a name.
_wrap = TokenWrapper(r"[|<>!@]?[A-Za-z0-9_.%]+|[\s\S]")


LANGUAGE = Language(
    "SendStuff",
    "sendstuff",
    category="other",
    boolean=sendstuff,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=_wrap,
    eof="an exhausted Input or InputNumber sends nothing, as the spec says",
    proof_workspace=(workspace, True, (3, 4, 5, 6, 7)),
)
