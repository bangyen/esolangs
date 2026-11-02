"""Retrograde Boolean generator: a native reversible conditional tree.

Input setters visit cells 0..n-1 once; zero is a forward-inert half-toggle
and one a toggle. The tree preserves these bits, toggles answer cell n for
one, then ends there. Each conditional restores its input bit, pointer and
forward direction. Branch source is emitted into chunks, never recursively
concatenated. Shared rank preprocessing uses expected constant-time lookups
on O(log T)-bit words; construction and source are O(T).

Size:
    At most 14T+4n-13 characters; n=10 random 1847: 8,601 chars.
"""

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    subtree_ids,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

PAIR = ("\\", "*")


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
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    prefix = (TEMPLATE_CHAR + ">") * n
    # Canonical constant spans: [ablations.constant_fold].
    if ids[0][0] < 2:
        return prefix + ("*" if ids[0][0] else "")
    chunks = [prefix, "<" * n]

    def body(depth: int, k: int) -> None:
        if ids[depth][k] == 0:
            return
        chunks.append(">")
        tree(depth, k)
        chunks.append("<")

    def tree(depth: int, k: int) -> None:
        node = ids[depth][k]
        # Fold the whole constant suffix: [ablations.constant_fold].
        if node < 2:
            # body() drops zero nodes; a constant here is always one.
            chunks.extend((">" * (n - depth), "*", "<" * (n - depth)))
            return
        zero, one = 2 * k, 2 * k + 1
        # Equal sibling functions ignore this input: [ablations.ignored_input].
        if ids[depth + 1][zero] == ids[depth + 1][one]:
            body(depth + 1, zero)
            return
        chunks.append("*{{*")
        body(depth + 1, one)
        chunks.append("}{*")
        body(depth + 1, zero)
        chunks.append("}}")

    tree(0, 0)
    chunks.append(">" * n)
    return _moves("".join(chunks))


LANGUAGE = Language(
    "Retrograde",
    "retrograde",
    category="tape_based",
    boolean=retrograde,
    wrap=wrap_chars,
    contract=BooleanContract(
        answer_mode="dump",
        note="Inputs are ordered one-instruction setters; the final current "
        "tape bit is the whole answer dump.",
    ),
    example=Example(pair=PAIR),
)
