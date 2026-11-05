"""SendStuff Boolean program generator: a shared decision diagram.

Distinct subtables share named nodes; the single-use root is anonymous.
Definitions precede their users.  A node is an
``Input``, which reads the next ``0`` (48) or ``1`` (49) whatever it
receives; ``Subtract 49`` passes only a 1, and ``Divide 48`` (48 // 48 is
1, 48 // 49 is 0) then ``Subtract 1`` only a 0, so each bit reaches one
child.  The macros ``!o`` and ``!z`` write the two branches and ``!y`` an ``Input``
with its ``!o`` (-19% to -22% at n=7..10 on random tables).  A node whose
halves agree reads its bit and sends on; a constant subtable is a chain
reading the remaining inputs into ``Constant 48`` or ``49`` and Output.
Names are ``subtree_ids`` ids, the chains ``z<depth>``/``o<depth>``.
Last-input identity and negation use the constant reader with a unary tail.

Size:
    O(T) size and build time: at most T - 1 diagram nodes and 2n chain nodes;
    n=8 constant zero: 87 chars; n=10 parity: 398 chars, n=10 random 1847: 4,091 chars.
    Last-input identity/negation: 8n+9 / 8n+30 chars.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_MACROS = "@o(>(Subtract 49>%))@z(>(Divide 48>(Subtract 1>%)))@y(Input!o %)"


def sendstuff(truth_table: str) -> str:
    """Build a SendStuff program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    constant = truth_table.count(truth_table[0]) == len(truth_table)
    last_input = not constant and truth_table == truth_table[:2] * (
        len(truth_table) // 2
    )
    if constant or last_input:
        # Last-input unary families share the reader, preserving every read.
        tail = (
            ("(Divide 48>(Add 48>(Output)))" if truth_table[0] == "1" else "(Output)")
            if last_input
            else f"(Constant {48 + int(truth_table[0])}>(Output))"
        )
        return ">" + "(Input>" * n + tail + ")" * n
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
                body = f"!y {name(depth + 1, 2 * k + 1)} !z {name(depth + 1, 2 * k)}"
                below |= {2 * k, 2 * k + 1}
            levels[depth][here] = f"|{here}({body})"
        frontier = below
    nodes = [node for level in reversed(levels) for node in level.values()]
    # The root has one reference and is already last in parser order.
    root = nodes.pop()
    body = root[len(name(0, 0)) + 2 : -1]
    return "".join([_MACROS, *nodes, ">(", body, ")"])


#: Break between words: a newline inside ``>17``, ``>%`` or ``!o`` splits a name.
_wrap = TokenWrapper(r"[|<>!@]?[A-Za-z0-9_.%]+|[\s\S]")


LANGUAGE = Language(
    "SendStuff",
    RuntimeSpec(
        "sendstuff",
        category="other",
        eof="an exhausted Input or InputNumber sends nothing, as the spec says",
    ),
    backend=BooleanBackend(generate=sendstuff, wrap=_wrap),
    contract=BooleanContract(input_shape="char_stream"),
)
