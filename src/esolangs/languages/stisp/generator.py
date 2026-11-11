"""Stisp Boolean program generator: a decision diagram walked by frames.

The head is a node atom or a pair of child expressions. Each input is one
frame ``->s[b]``; native list-pattern equations select a pair's child,
while named nodes use one or two equations. Leaves ``0`` and ``1`` drain
remaining frames. For AND:

    (l h)->s[0]=l;(l h)->s[1]=h;c->s[x]=c;(0 (0 1))->s[$]->s[$]

A bottom-up cost rule inlines cheap private nodes and names shared ones.
Each literal head carries at most 2n atom bytes, matching the input frames'
16n-bit payload. Written workspace is at most 32n bits before the halt dump.
There are O(T/n) distinct nodes, so their O(n)-character representations
also build in O(T) time.

Size:
    O(T) text: one or two equations a node of the reduced diagram;
    n=4 parity: 139 chars, n=10 random 1847: 1,964 chars.
    Constants match the input list once: 2n+15 chars (15 at n=1), one rewrite
    plus the halt dump, and at most 8n+8 written bits before the dump.

Decisions:
    Ids repeat only within a level (:func:`subtree_ids`), so equal subtables
    share a node.
"""

from collections import Counter

from esolangs.generation.decision import decision_layers
from esolangs.generation.helpers import (
    _validate_truth_table,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_fragments,
)

#: Each input is one atom, ``0`` or ``1``, inside its frame.
_INPUT = InputSlot(1)
#: The drain: under a leaf every remaining frame rewrites to the leaf.
_DRAIN = "c->s[x]=c;"
#: Native list-head selectors precede the variable-head drain.
_CONS = "(l h)->s[0]=l;(l h)->s[1]=h;"
#: A newline is whitespace, legal anywhere but inside an identifier or ``->``.


def stisp(truth_table: str) -> str:
    """Build a Stisp template whose result is ``truth_table[row]``."""
    return _layout(truth_table).source


def _layout(truth_table: str) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        head: tuple[TemplateToken, ...] = (_INPUT,)
        if n > 1:
            head = ("(", *(_INPUT, " ") * (n - 1), _INPUT, ")")
        return layout_fragments((f"x->s[]={truth_table[0]};", *head, "->s[]"))
    diagram = decision_layers(truth_table)
    nodes = {
        node: pair
        for layer in diagram.children
        for node, pair in layer.items()
        if node >= 2
    }
    uses = Counter({diagram.root: 1})
    for lo, hi in nodes.values():
        uses[lo] += 1
        if lo != hi:
            uses[hi] += 1
    heads = {0: "0", 1: "1"}
    payload = {0: 1, 1: 1}
    definitions: dict[int, str] = {}
    named: set[int] = set()
    # Callers are still named when a node is priced, so its original use
    # count is exactly the number of replacements at this bottom-up step.
    for node, (lo, hi) in reversed(list(nodes.items())):
        low, high = heads[lo], heads[hi]
        name = str(node)
        equation = (
            f"{name}->s[x]={low};"
            if lo == hi
            else f"{name}->s[0]={low};{name}->s[1]={high};"
        )
        definitions[node] = equation
        literal = f"({low} {high})"
        size = payload[lo] + payload[hi]
        # Give the head at most the input frames' 16n bits. With D=O(T/n)
        # distinct nodes, each O(n)-character spelling also builds in O(T).
        # [ablations.trick_prototype_20261102_bounded_literals]
        if size <= 2 * n and uses[node] * len(literal) < len(equation) + uses[
            node
        ] * len(name):
            heads[node], payload[node] = literal, size
        else:
            heads[node], payload[node] = name, len(name)
            named.add(node)
    prefix = _CONS if len(named) != len(nodes) else ""
    equations = "".join(definitions[node] for node in nodes if node in named)
    return layout_fragments(
        (prefix + equations + _DRAIN + heads[diagram.root], *("->s[", _INPUT, "]") * n)
    )


def stisp_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table)
