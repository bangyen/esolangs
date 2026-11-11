"""FRACTRAN Boolean program generator: a tree whose equal subtables share a state.

Each input is the exponent of its own prime in the starting value; a state
prime is a node, its two fractions test one input and the first-match rule
is the else-branch.  Sharing makes the tree a reduced decision diagram, at
most ``min(2**d, 2**2**(n - d))`` states at depth ``d``, ``O(T / log T)``
in all, each written in ``O(log T)`` digits.  Every base is a prime below the
text's length, which the interpreter's index factors and buckets by state.

Size:
    Worst-case Theta(T) text, at most ``n`` fractions fire a run; n=10 parity: 342
    chars, n=10 random 1847: 4,397 chars. Constants omit the state prime:
    at most n+1 commands including the halt; n=8: 71/75 chars.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import islice
from typing import Any

from esolangs.factor_primes import prime_segments
from esolangs.generation.decision import reduced_diagram
from esolangs.generation.fraction_templates import fraction_template, wrap_fractions
from esolangs.generation.helpers import (
    _validate_truth_table,
    layout_width,
    same_tokens,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import TemplateLayout
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import balance_score
from esolangs.languages.fractran.interpreter.index import SMALL_BASE

#: How each input is set: the exponent of its prime in the starting value.
#: Each exponent occupies one source character.


@dataclass(frozen=True)
class _Leaf:
    """A leaf of the diagram: the answer, and the level it stops reading at."""

    answer: str
    depth: int


@dataclass(frozen=True)
class _Node:
    """An internal node: the input it reads, and its children's indices."""

    depth: int
    zero: int
    one: int


def _primes(count: int) -> list[int]:
    """Return the first ``count`` primes, 2 first."""
    stream = (prime for *_, segment in prime_segments(count + 2) for prime in segment)
    return list(islice(stream, count))


def _tree(truth_table: str, n: int) -> list[_Leaf | _Node]:
    """Return the decision diagram, post-order, root last."""
    diagram, root = reduced_diagram(truth_table, n)
    seen: dict[int, int] = {}
    nodes: list[_Leaf | _Node] = []

    def walk(key: int) -> int:
        if key not in seen:
            if key < 2:
                nodes.append(_Leaf(str(key), n))
            else:
                entry = diagram[key]
                zero, one = walk(entry.zero), walk(entry.one)
                nodes.append(_Node(entry.level, zero, one))
            seen[key] = len(nodes) - 1
        return seen[key]

    # First-encounter postorder keeps native state-prime assignment stable.
    walk(root)
    return nodes


def _nodes(
    nodes: list[_Leaf | _Node], states: list[int], inputs: list[int]
) -> list[str]:
    """Return two fractions per node; leaf edges carry the answer directly."""
    fractions: list[str] = []
    for index, entry in enumerate(nodes):
        if isinstance(entry, _Leaf):
            continue
        # The one-child first: the zero-child is the else, by priority.
        # A large guard is spelled as its primes, which the index factors.
        one, zero = entry.one, entry.zero
        state, bit = states[index], inputs[entry.depth]
        product = state * bit
        guard = product if product <= SMALL_BASE else f"{state}*{bit}"
        fractions.append(f"{states[one]}/{guard}")
        fractions.append(f"{states[zero]}/{state}")
    return fractions


def _unread(nodes: list[_Leaf | _Node], n: int) -> set[int]:
    """Return the inputs some path never reads: each needs a clear.

    A path skips the depths an edge jumps over, and a leaf skips every depth
    from its own down.
    """
    unread = set(range(nodes[-1].depth))
    for entry in nodes:
        if isinstance(entry, _Leaf):
            unread.update(range(entry.depth, n))
        else:
            for child in (entry.zero, entry.one):
                unread.update(range(entry.depth + 1, nodes[child].depth))
    return unread


def _plain(truth_table: str, n: int, *, small_root: bool = False) -> TemplateLayout:
    """Return the table as a decision diagram: every level read.

    Only ``2`` is reserved, so the inputs and states take the smallest primes
    there are, and a run is a step a level and a clear for
    each input a path left unread.
    """
    nodes = _tree(truth_table, n)
    primes = _primes(1 + n + sum(isinstance(entry, _Node) for entry in nodes))
    inputs = primes[1 : 1 + n]
    state_primes = iter(primes[1 + n :])
    # Leaf edges remove one command on every nonconstant run; see
    # [ablations.leaf_inline]. Only internal nodes need state primes.
    states = [
        1 + int(entry.answer) if isinstance(entry, _Leaf) else next(state_primes)
        for entry in nodes
    ]
    if small_root:
        first = next(i for i, entry in enumerate(nodes) if isinstance(entry, _Node))
        states[first], states[-1] = states[-1], states[first]
    fractions = _nodes(nodes, states, inputs)
    unread = _unread(nodes, n)
    fractions += [f"1/{p}" for depth, p in enumerate(inputs) if depth in unread]
    return fraction_template(inputs, fractions, root=str(states[-1]))


def _widest(program: str) -> int:
    """Return the longest token's length."""
    return max(map(len, program.split()))


def fractran(truth_table: str, width: int | None = None) -> str:
    """Return a template; narrow tables give the root the smallest state prime.

    Halts at 1 or 2 for zero or one; input-prime exponents are filled by ``PAIR``.
    """
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        bit = int(truth_table[0])
        inputs = _primes(n + bit)[bit:]
        layout = fraction_template(
            inputs, [f"1/{prime}" for prime in inputs], root="2" if bit else ""
        )
        return wrap_fractions(layout, width)
    layout = _plain(truth_table, n)
    if width is None:
        return layout
    floor = _widest(layout.source)
    if floor > width:
        narrow = _plain(truth_table, n, small_root=True)
        if _widest(narrow.source) < floor:
            layout = narrow
    return wrap_fractions(layout, width)


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Fractions tokenize on whitespace; short setters keep the old pair."""
    return any(
        same_tokens(template, program)
        for program in (layout(1), layout(layout_width(template)), plain)
    )


def fractran_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def fractran_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Return the default or its fractions at the squarest token width."""
    layout = request.source
    if not isinstance(layout, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    tokens = layout.source.split()
    width = balanced_token_width(tokens, " ", minimum=max(map(len, tokens)))
    fitted = wrap_fractions(layout, width)
    return min(layout, fitted, key=lambda candidate: balance_score(candidate.source))
