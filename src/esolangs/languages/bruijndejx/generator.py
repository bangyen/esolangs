r"""Bruijndejx Boolean program generator: a shared decision tree of ``?`` reads.

``Q = [[1 0 1?:.]]`` is the two-way read: ``one zero Q:`` reads a bit and
continues with ``zero`` or ``one``, and with ``zero`` at EOF, so a missing
input reads as 0.  ``I = [0 0 0?:.]`` reads a bit (or EOF) and continues
with its one argument, so an input a residual ignores costs ``I.``.  Leaves
``*/.`` and ``*\.`` write their bit and halt.  A residual with two or more
parent edges is declared once under a short name and referenced; the rest
are inline, so each residual's text appears once.  The root is the last
item, a bare expression; inputs are read first to last, the answer after
the last read.

Both that shared form and the all-inline tree are priced arithmetically and
only the shorter is built, so generation stays O(T).

Size:
    O(T): at most 5T + 23 chars, the inline tree's bound (exact max
    n = 2..4): 3T leaf + 2(T - 1) branch chars + the 15-char ``Q`` header;
    a fold saves at least a 3-char leaf and the ``I`` header costs 13.
    n=4 parity: 69 chars, n=10 random 1847: 1,218 chars.  Constant
    tables: 2n + 16.

Decisions:
    Names alone are O(T log T) at worst, as identifiers lengthen with their
    count; the race keeps the inline bound.  At n=10 random 1847 the inline
    tree is 3,875 chars, every residual named 2,594, multi-parent residuals
    named 1,218 ([ablations.named_sharing_20261117]).
"""

from esolangs.generation.helpers import _validate_truth_table
from esolangs.generation.projection import _residual_ids
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program

__all__ = ["bruijndejx"]

_LEAF = ("*/.", "*\\.")
_BRANCH = "Q=[[1 0 1?:.]];"
_IGNORE = "I=[0 0 0?:.];"
_FIRST = "abcdefghijklmnopqrstuvwxyzABCDEFGHJKLMNOPRSTUVWXYZ_"
_REST = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'"


def _name(k: int) -> str:
    """Return the ``k``-th identifier, shortest first, never ``Q`` or ``I``."""
    text = _FIRST[k % len(_FIRST)]
    k //= len(_FIRST)
    while k:
        k -= 1
        text += _REST[k % len(_REST)]
        k //= len(_REST)
    return text


def _name_length(k: int) -> int:
    length, block = 1, len(_FIRST)
    while k >= block:
        k -= block
        block *= len(_REST)
        length += 1
    return length


def bruijndejx(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` after reading every input."""
    n = _validate_truth_table(truth_table)
    diagram = _residual_ids(truth_table, n)
    children = diagram.children
    root = diagram.levels[0][0]
    order = [node for level in reversed(diagram.levels[:n]) for node in level]
    parents = dict.fromkeys(order, 0)
    for node in order:
        for child in set(children[node]):
            if child >= 2:
                parents[child] += 1
    # Names in node order: ranking by parent count saved 0% at n = 7, 8 and
    # 0.46% at n = 11 (retired 2026-11-27); names stay one letter to n = 10.
    rank = {node: k for k, node in enumerate(n for n in order if parents[n] >= 2)}

    def price(named: dict[int, int]) -> tuple[int, bool, bool]:
        """Return total chars and whether ``Q`` and ``I`` are used."""
        size = {0: 3, 1: 3}
        branch = ignore = False
        total = 0
        for node in order:
            zero, one = children[node]
            cost = [
                _name_length(named[c]) + 1 if c in named else size[c]
                for c in (zero, one)
            ]
            if zero == one:
                size[node] = cost[0] + 2
                ignore = True
            else:
                size[node] = cost[0] + cost[1] + 2
                branch = True
            if node in named:
                total += _name_length(named[node]) + 2 + size[node]
        total += size[root] + len(_BRANCH) * branch + len(_IGNORE) * ignore
        return total, branch, ignore

    named = rank if price(rank)[0] < price({})[0] else {}
    _, branch, ignore = price(named)
    texts = {0: _LEAF[0], 1: _LEAF[1]}
    declarations = [_BRANCH * branch, _IGNORE * ignore]

    def ref(child: int) -> str:
        return _name(named[child]) + " " if child in named else texts[child]

    for node in order:
        zero, one = children[node]
        text = ref(zero) + "I." if zero == one else ref(one) + ref(zero) + "Q:"
        if node in named:
            declarations.append(f"{_name(named[node])}={text};")
        else:
            texts[node] = text
    return "".join(declarations) + texts[root]


def bruijndejx_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return bruijndejx(request.table)
