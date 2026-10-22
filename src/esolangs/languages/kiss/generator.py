"""Kiss Boolean program generator: the table's decision tree, read by ``S``.

A node is ``S(A)(B)``: with two arguments the head ``S`` reads a bit and
continues as ``A`` on 0, ``B`` on 1.  A leaf is ``KK``, which outputs 0 and
halts on the ``K`` left, or ``SK``, which outputs 1 and halts.  A node whose
halves agree above the leaves still reads its bit, as ``SS(SKK)X``: that
reduces to ``S X (SKK X)``, whose two branches both reach ``X``, written
once.

Size:
    Theta(T) text worst case, 7 chars a row on parity; n=4 parity: 107
    chars, n=10 parity: 7,163 chars.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Each leaf outputs its bit and halts.
_LEAF = {"0": "KK", "1": "SK"}
#: Reads a bit and continues with the term that follows, either way.
_SKIP = "SS(SKK)"


def kiss(truth_table: str) -> str:
    """Build a Kiss program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    parts: list[str] = []
    # A stack of nodes and closing text, emitted in order: O(T).
    work: list[tuple[int, int] | str] = [(0, 0)]
    while work:
        item = work.pop()
        if isinstance(item, str):
            parts.append(item)
            continue
        depth, k = item
        if depth == n:
            parts.append(_LEAF[truth_table[k]])
            continue
        lo, hi = 2 * k, 2 * k + 1
        # The skip costs 9 chars against a second copy; a 2-char leaf is
        # cheaper written twice.
        if depth + 1 < n and ids[depth + 1][lo] == ids[depth + 1][hi]:
            parts.append(_SKIP + "(")
            work += [")", (depth + 1, lo)]
        else:
            parts.append("S(")
            work += [")", (depth + 1, hi), ")(", (depth + 1, lo)]
    return "".join(parts)


LANGUAGE = Language(
    "Kiss",
    "kiss",
    category="other",
    boolean=kiss,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=wrap_chars,
    empty_program="a Kiss program needs at least one combinator",
)
