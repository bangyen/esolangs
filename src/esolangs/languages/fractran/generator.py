"""FRACTRAN Boolean program generator: a tree whose equal subtables share a state.

Each input is the exponent of its own prime in the starting value; a state
prime is a node, its two fractions test one input and the first-match rule
is the else-branch.  Sharing makes the tree a reduced decision diagram, at
most ``min(2**d, 2**2**(n - d))`` states at depth ``d``, ``O(T / log T)``
in all, each written in ``O(log T)`` digits.  Every base is a prime below the
text's length, which the interpreter's index factors and buckets by state.

Size:
    Theta(T) text, at most ``n + 1`` fractions fire a run; n=10 parity: 364
    chars, n=10 random 1847: 4,466 chars.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import islice
from typing import Any

from esolangs.factor_primes import prime_segments
from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    layout_width,
    same_tokens,
    subtree_ids,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import (
    _join_tokens,
    balance_score,
    wrap_program,
    wrap_space_delimited,
)
from esolangs.languages.fractran.interpreter.index import SMALL_BASE
from esolangs.languages.fractran.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

#: How each input is set: the exponent of its prime in the starting value.
#: One digit wide, so the run is one :data:`TEMPLATE_CHAR`.
PAIR = ("0", "1")


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
    ids = subtree_ids(truth_table)
    seen: dict[tuple[int, int], int] = {}
    nodes: list[_Leaf | _Node] = []

    def walk(depth: int, lo: int, hi: int) -> int:
        # Equal subtables at one depth share one state: a DAG, not a tree.
        key = (depth, ids[depth][lo >> (n - depth)])
        if key not in seen:
            if depth == n:
                # No early exit on a constant span: the halves-agree skip
                # collapses one to a single shared leaf, while an early
                # leaf per depth cost size on AND ([ablations.constant_fold]).
                nodes.append(_Leaf(truth_table[lo], depth))
            else:
                mid = (lo + hi) // 2
                zero = walk(depth + 1, lo, mid)
                one = walk(depth + 1, mid, hi)
                if zero == one:
                    seen[key] = zero  # halves agree: this input is never read
                    return zero
                nodes.append(_Node(depth, zero, one))
            seen[key] = len(nodes) - 1
        return seen[key]

    walk(0, 0, len(truth_table))
    return nodes


def _nodes(
    nodes: list[_Leaf | _Node], states: list[int], inputs: list[int]
) -> list[str]:
    """Return the diagram's fractions: a leaf's answer, a node's two."""
    fractions: list[str] = []
    for index, entry in enumerate(nodes):
        if isinstance(entry, _Leaf):
            fractions.append(f"{2 if entry.answer == '1' else 1}/{states[index]}")
        else:
            # The one-child first: the zero-child is the else, by priority.
            # A large guard is spelled as its primes, which the index factors.
            one, zero = entry.one, entry.zero
            state, bit = states[index], inputs[entry.depth]
            product = state * bit
            guard = product if product <= SMALL_BASE else f"{state}*{bit}"
            fractions.append(f"{states[one]}/{guard}")
            fractions.append(f"{states[zero]}/{state}")
    return fractions


def _start(states: list[int], inputs: list[int]) -> str:
    """Return the starting value: the root's state, and each input's run."""
    return "*".join(
        [str(states[-1])] + [f"{prime}^{TEMPLATE_CHAR}" for prime in inputs]
    )


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


def _plain(truth_table: str, n: int, *, small_root: bool = False) -> str:
    """Return the table as a decision diagram: every level read.

    Only ``2`` is reserved, so the inputs and states take the smallest primes
    there are, and a run is a step a level, one for the leaf, and a clear for
    each input a path left unread.
    """
    nodes = _tree(truth_table, n)
    primes = _primes(1 + n + len(nodes))
    inputs, states = primes[1 : 1 + n], primes[1 + n :]
    if small_root:
        states[0], states[-1] = states[-1], states[0]
    fractions = _nodes(nodes, states, inputs)
    unread = _unread(nodes, n)
    fractions += [f"1/{p}" for depth, p in enumerate(inputs) if depth in unread]
    return " ".join([_start(states, inputs), *fractions])


def _widest(program: str) -> int:
    """Return the longest token's length."""
    return max(map(len, program.split()))


def fractran(truth_table: str, width: int | None = None) -> str:
    """Return a template; narrow tables give the root the smallest state prime.

    Halts at 1 or 2 for zero or one; input-prime exponents are filled by ``PAIR``.
    """
    n = _validate_truth_table(truth_table)
    program = _plain(truth_table, n)
    if width is None:
        return program
    floor = _widest(program)
    if floor > width:
        narrow = _plain(truth_table, n, small_root=True)
        if _widest(narrow) < floor:
            program = narrow
    return wrap_program(program, "fractran", width)


def _balance(_table: str, default: str) -> str:
    """Return the default or its fractions joined at the squarest token width."""
    tokens = default.split()
    width = balanced_token_width(tokens, " ", minimum=_widest(default))
    return min([default, _join_tokens(tokens, width, " ")], key=balance_score)


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Fractions tokenize on whitespace; short setters keep the old pair."""
    return any(
        same_tokens(template, program)
        for program in (layout(1), layout(layout_width(template)), plain)
    )


LANGUAGE = Language(
    "FRACTRAN",
    "fractran",
    category="register_based",
    boolean=fractran,
    same_layout=_same_layout,
    contract=BooleanContract(
        answer_mode="dump",
        answer_values=("1", "2"),
        note="FRACTRAN has neither input nor output: the inputs are the "
        "exponents of n primes in the starting value, and the answer "
        "is the value the run stops on -- 1 for a zero and 2 for a one",
    ),
    # Whitespace- or comma-separated tokens, and a break inside one would
    # change a number.
    wrap=wrap_space_delimited,
    balance=_balance,
    empty_program="a FRACTRAN program needs a starting value",
    example=Example(pair=PAIR, expected="1"),
    proof_execution=(execution, True, (3, 5)),
    proof_workspace=(workspace, True, (3, 5, 6)),
)
