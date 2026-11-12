"""Quassaunt Boolean generator: shared residuals and one definition-store loop.

Every input depth reads once. Equal halves share a chain; other nodes use
``%%Ifdisjoint`` on the read character and ``{1}`` to choose a child.
Globals use frequency-ranked base-89 names; ``[]`` holds ``{1}``.

A helper stores the queued name/body/key triples, then an empty dummy key
selects the root. Two empty strings per input supply the discarded operands
of singleton ``%%Concatenateall`` calls. Constants read and print directly.

Size:
    O(T) size and construction: O(T/log T) residuals with logarithmic names.
    n=10 random 1847: 33,170 chars, n=10 parity: 3,062 chars.
    Constants use 12n + 20 chars and n + 2 commands; n=8 zero: 116 chars.

Decisions:
    The store loop trades more executed words and workspace for source size
    ([ablations.word_economy]). ``[]`` is a bracketed global name.
"""

from collections import Counter
from math import isqrt
from typing import NamedTuple

from esolangs.generation.helpers import _validate_truth_table, short_name, subtree_ids
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.token_balance import CELL_ASPECT, balanced_token_width
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.runtime._program import Program


class _Node(NamedTuple):
    kind: str
    bit: int
    children: tuple[str, ...]


# Exclude code separators/brackets, helper-name '_' and reserved [Whitespace].
_ALPHABET = "".join(chr(i) for i in range(33, 127) if chr(i) not in "?[]_W")


def _graph(table: str, n: int) -> dict[str, _Node]:
    """Reachable residuals, retaining one read for every input depth."""
    ids = subtree_ids(table)

    def key(depth: int, slot: int) -> str:
        sub = ids[depth][slot]
        return "zo"[sub] + str(depth) if sub < 2 else str(sub)

    nodes: dict[str, _Node] = {}
    frontier = {0}
    for depth in range(n + 1):
        below: set[int] = set()
        for slot in sorted(frontier):
            here = key(depth, slot)
            if here in nodes:
                continue
            sub = ids[depth][slot]
            zero, one = 2 * slot, 2 * slot + 1
            if depth == n:
                node = _Node("leaf", sub, ())
            elif sub < 2 or ids[depth + 1][zero] == ids[depth + 1][one]:
                node = _Node("chain", sub, (key(depth + 1, zero),))
                below.add(zero)
            else:
                node = _Node("branch", sub, (key(depth + 1, zero), key(depth + 1, one)))
                below.update((zero, one))
            nodes[here] = node
        frontier = below
    return nodes


def _dense_names(nodes: dict[str, _Node]) -> dict[str, str]:
    """Assign the shortest names to the most frequent references; ties stay stable."""
    counts = Counter(dict.fromkeys(nodes, 1))
    counts[next(iter(nodes))] += 1
    for node in nodes.values():
        counts.update(node.children)
    return {
        key: short_name(rank, _ALPHABET)
        for rank, key in enumerate(sorted(nodes, key=lambda key: -counts[key]))
    }


def _code(name: str, *, fillers: bool = False) -> str:
    """Obtain singleton code, using two explicit fillers only at startup."""
    return ("@@?@@?" if fillers else "") + f"@@[{name}]?%%Obtain?@@?%%Concatenateall"


def _node_body(node: _Node, names: dict[str, str]) -> str:
    """Read once and tail-call the selected child, or print at a leaf."""
    if node.kind == "leaf":
        return f"@@{node.bit}?%%Printtoconsole"
    if node.kind == "chain":
        return "%%Inputchar?" + _code(names[node.children[0]]) + "?%%Evaluatereplace"
    zero, one = (names[child] for child in node.children)
    return (
        f"@@@@[{zero}]?%%Inputchar?%%Empty?%%Makecontain?@@@@[{one}]?"
        "@@[]?%%Obtain?%%Ifdisjoint?%%Obtain?@@?%%Concatenateall?%%Evaluatereplace"
    )


def _store_loop(root: str) -> str:
    """Store a triple; its empty dummy key selects the root after the last triple."""
    return (
        "@@d?%%Swap?%%Empty?%%Makecontain?%%Store?%%Empty?%%Makecontain?%%Store?"
        "@@?@@?@@@@[_s]?@@d?%%Obtain?@@@@[" + root + "]?@@?%%Empty?%%Makecontain?"
        "%%Ifdisjoint?%%Obtain?@@?%%Concatenateall?%%Evaluatereplace"
    )


def quassaunt(truth_table: str) -> str:
    """Build a Quassaunt program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        return "%%Inputchar " * n + f"@@{truth_table[0]} %%Printtoconsole"
    nodes = _graph(truth_table, n)
    names = _dense_names(nodes)
    root = names[next(iter(nodes))]
    definitions = [
        (f"[{names[key]}]", _node_body(node, names)) for key, node in nodes.items()
    ]
    definitions.append(("[]", "1"))
    # [ablations.word_economy]: every path consumes at most two fillers per bit.
    parts = [
        "@@[_s] @@" + _store_loop(root) + " %%Empty %%Makecontain %%Store",
        "@@ " * (2 * n) + "@@[_x] @@ @@",
        *(f"@@{key} @@{body} @@{key}" for key, body in definitions),
        _code("_s", fillers=True).replace("?", " ") + " %%Evaluate",
    ]
    return " ".join(parts)


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


#: Fixed limit for compact programs: an uncut body pins their width.
#: [ablations.balance_cut] records why the race was replaced; the new helper's
#: geometry is measured separately in [ablations.word_economy].
_CUT = 64


def _balance(_table: str, default: str) -> str:
    """The squarest wrap, cutting words when the program is narrower than one."""
    words = default.split()
    if isqrt(CELL_ASPECT * len(default)) < max(map(len, words)):
        words = [t for w in words for t in _cut(w, _CUT)]
    return wrap_space_delimited(" ".join(words), balanced_token_width(words, " "))


def quassaunt_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return quassaunt(request.table)


def quassaunt_balance_request(request: BalanceRequest) -> Program:
    """Lay out source through the declared balance request interface."""
    return _balance(request.table, request.text_source())
