"""Retrograde Boolean generator: a native reversible conditional tree.

Input setters visit cells 0..n-1 once; zero is a forward-inert half-toggle
and one a toggle. The tree preserves these bits, toggles answer cell n for
one, then ends there. A single turn can select the forward/backward
functions of one child; constant half-toggles seed input literals. Each
conditional restores its input bit, pointer and entry direction. Source
is emitted into chunks. Rank preprocessing uses expected constant-time
lookups on O(log T)-bit words; construction and source are O(T).

Size:
    At most 14T+4n-13 characters; n=10 random 1847: 6,794 chars.
"""

from esolangs.generation.helpers import (
    subtree_ids,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.template import InputSlot, TemplateLayout, layout_fragments

_INPUT = InputSlot(1)


def _moves(source: str) -> str:
    """Cancel adjacent inverse moves, valid in either direction of execution."""
    # Minimal spelling, in either direction: [ablations.inverse_moves].
    reduced: list[str] = []
    for c in source:
        if reduced and reduced[-1] + c in ("><", "<>"):
            reduced.pop()
        else:
            reduced.append(c)
    return "".join(reduced)


def retrograde(truth_table: str) -> str:
    """Return a template whose final current cell is the requested answer."""
    return _layout(truth_table).source


def _layout(truth_table: str) -> TemplateLayout:
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    prefix = (*(_INPUT, ">") * (n - 1), _INPUT)
    if ids[0][0] < 2:
        return layout_fragments((*prefix, ">*" if ids[0][0] else ">"))
    backs = [list(level) for level in ids]
    kinds = [[""] * len(level) for level in ids]
    fresh = max(map(max, ids)) + 1
    # Intern the backward functions of chosen blocks from child ids.
    # For example, 0010 runs backward as 0001 (see the ablation record).
    # The map is an involution, so testing the one child covers both orientations.
    for depth in reversed(range(n)):
        rank = {
            tuple(ids[depth + 1][2 * k : 2 * k + 2]): sub
            for k, sub in enumerate(ids[depth])
            if sub >= 2
        }
        for k, node in enumerate(ids[depth]):
            if node < 2:
                continue
            z, o = ids[depth + 1][2 * k : 2 * k + 2]
            zb, ob = backs[depth + 1][2 * k : 2 * k + 2]
            if z == o:
                kind = "skip"
                low = high = zb
            elif z < 2 and o < 2:
                kind = "literal"
                low, high = o, z
            elif ob == z:
                kind = "one"
                low, high = o, z
            else:
                kind = "branch"
                low, high = zb, ob
            kinds[depth][k] = kind
            # Reversal is constant iff its subtree is; this node is nonconstant.
            key = low, high
            if key not in rank:
                rank[key] = fresh
                fresh += 1
            backs[depth][k] = rank[key]
    # [ablations.trick_prototype_20261102_bidirectional_sibling]
    chunks = [">", "<" * n]
    stack: list[str | tuple[int, int]] = [(0, 0)]
    while stack:
        task = stack.pop()
        if isinstance(task, str):
            chunks.append(task)
            continue
        depth, k = task
        node = ids[depth][k]
        kind = kinds[depth][k]
        z, o = 2 * k, 2 * k + 1
        parts: list[str | tuple[int, int]]
        if node < 2:
            # Branch tasks omit zero children; skip/one tasks cannot select zero.
            parts = [">" * (n - depth), "*", "<" * (n - depth)]
        elif kind == "skip":
            parts = [">", (depth + 1, z), "<"]
        elif kind == "literal":
            parts = [
                "*{",
                ">" * (n - depth),
                "/" if ids[depth + 1][o] else "\\",
                "<" * (n - depth),
                "}*",
            ]
        elif kind == "one":
            parts = ["*{", ">", (depth + 1, o), "<", "}*"]
        else:
            parts = ["*{{*"]
            if ids[depth + 1][o]:
                parts += [">", (depth + 1, o), "<"]
            parts += ["}{*"]
            if ids[depth + 1][z]:
                parts += [">", (depth + 1, z), "<"]
            parts += ["}}"]
        stack.extend(reversed(parts))
    chunks.append(">" * n)
    return layout_fragments((*prefix, _moves("".join(chunks))))


def retrograde_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table)
