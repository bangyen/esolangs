"""Quassaunt Boolean program generator: a shared decision diagram.

Every distinct subtable's code is stored once, as a one-string set in a
global ``[id]``, and a node runs a child by obtaining it and turning the
set back into its string (the wiki's ``@@ %%Swap @@ %%Swap @@
%%Concatenateall``, here as ``@@?@@?@@[id]?%%Obtain?@@?%%Concatenateall``).
A branching node pushes its 1-child's code, the set ``{2, c}`` of the
character it reads, its 0-child's code and ``{1}``: ``{1}`` is a proper
subset only when ``c`` is ``1``, so ``%%Ifpropersubset`` runs the right
child.  A node whose halves agree, and a constant subtable's chain, reads
its bit into a local and runs its child with ``%%Evaluatereplace``.
Names are ``subtree_ids`` ids, the chains ``z<depth>``/``o<depth>``.

Size:
    O(T) size and build time: at most T - 1 diagram nodes and 2n chain
    nodes; n=10 random 1847: 51,591 chars, n=10 parity: 4,296 chars.
"""

from math import isqrt

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.token_balance import CELL_ASPECT, balanced_token_width
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.quassaunt.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def _code(name: str) -> str:
    """Push the code stored under ``[name]``, as ``?``-separated words."""
    return f"@@?@@?@@[{name}]?%%Obtain?@@?%%Concatenateall"


def quassaunt(truth_table: str) -> str:
    """Build a Quassaunt program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)

    def name(depth: int, k: int) -> str:
        sub = ids[depth][k]
        return "zo"[sub] + str(depth) if sub < 2 else str(sub)

    # Reachable nodes; stored code is only looked up when it runs.
    nodes: dict[str, str] = {}
    frontier = {0}
    for depth in range(n + 1):
        below: set[int] = set()
        for k in sorted(frontier):
            sub, here = ids[depth][k], name(depth, k)
            if here in nodes:
                continue
            zero, one = 2 * k, 2 * k + 1
            if depth == n:
                body = f"@@{sub}?%%Printtoconsole"
            elif sub < 2 or ids[depth + 1][zero] == ids[depth + 1][one]:
                body = (
                    "@@d?%%Inputchar?%%Empty?%%Makecontain?%%Store?"
                    f"{_code(name(depth + 1, zero))}?%%Evaluatereplace"
                )
                below.add(zero)
            else:
                body = (
                    f"{_code(name(depth + 1, one))}?@@2?%%Inputchar?%%Empty?"
                    f"%%Makecontain?%%Makecontain?{_code(name(depth + 1, zero))}?"
                    "@@1?%%Empty?%%Makecontain?%%Ifpropersubset"
                )
                below |= {zero, one}
            nodes[here] = f"@@[{here}] @@{body} %%Empty %%Makecontain %%Store"
        frontier = below
    start = _code(name(0, 0)).replace("?", " ") + " %%Evaluate"
    return " ".join([*nodes.values(), start])


def _cut(word: str, limit: int) -> list[str]:
    """Cut a ``@@`` word at ``?`` into ``%%Concatenate``-joined pieces."""
    if not word.startswith("@@") or len(word) <= limit:
        return [word]
    parts = word[2:].split("?")
    pieces: list[str] = []
    here = ""
    for i, part in enumerate(parts):
        piece = part + "?" * (i < len(parts) - 1)
        if here and len(here) + len(piece) > limit:
            pieces.append(here)
            here = piece
        else:
            here += piece
    pieces.append(here)
    out = ["@@" + pieces[0]]
    for piece in pieces[1:]:
        out += ["@@" + piece, "%%Concatenate"]
    return out


#: Piece limit.  A node body cannot wrap, so a compact program is as wide as its
#: longest word; cutting at 64 saves 35-88% of the balanced area on named
#: functions n=3..10 and 1.2% on random n=7, so only compact programs are cut
#: (the old race over six limits saved 13.8% n=7 and 5.3% n=8 on random).
_CUT = 64


def _balance(_table: str, default: str) -> str:
    """The squarest wrap, cutting words when the program is narrower than one."""
    words = default.split()
    if isqrt(CELL_ASPECT * len(default)) < max(map(len, words)):
        words = [t for w in words for t in _cut(w, _CUT)]
    return wrap_space_delimited(" ".join(words), balanced_token_width(words, " "))


LANGUAGE = Language(
    "Quassaunt",
    "quassaunt",
    category="stack_based",
    boolean=quassaunt,
    contract=BooleanContract(input_shape="char_stream"),
    # Whitespace separates words and a word holds none, so break only there.
    wrap=wrap_space_delimited,
    balance=_balance,
    proof_execution=(execution, True, (3, 6)),
    proof_workspace=(workspace, True, (3, 4, 5, 6)),
)
