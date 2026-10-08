"""FRACTRAN boolean templates: a decision tree whose equal subtables share a state.

Each input is the exponent of its own prime in the starting value; a state
prime is a node, its two fractions test one input and the first-match rule
is the else-branch.  Sharing makes the tree a reduced decision diagram, at
most ``min(2**d, 2**2**(n - d))`` states at depth ``d``, ``O(T / log T)``
in all, each written in ``O(log T)`` digits: ``Theta(T)`` text, and at most
``n + 1`` fractions fire a run.  Every base is a prime below the text's
length, which the interpreter's index factors and buckets by state.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice

from esolangs.interpreters.other.fractran.index import SMALL_BASE
from esolangs.tools.factor import _primes as _prime_stream
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    subtree_ids,
)

#: How each input is set: the exponent of its prime in the starting value.
#: One digit wide, so the run is one :data:`TEMPLATE_CHAR`.
PAIR = ("0", "1")


@dataclass(frozen=True)
class _Leaf:
    """A folded subtable: the answer, and the level it stops reading at."""

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
    return list(islice(_prime_stream(), count))


def _tree(truth_table: str, n: int) -> list[_Leaf | _Node]:
    """Return the decision diagram, post-order, root last."""
    constant = constant_span_test(truth_table)
    ids = subtree_ids(truth_table)
    seen: dict[tuple[int, int], int] = {}
    nodes: list[_Leaf | _Node] = []

    def walk(depth: int, lo: int, hi: int) -> int:
        # Equal subtables at one depth share one state: a DAG, not a tree.
        key = (depth, ids[depth][lo >> (n - depth)])
        if key not in seen:
            if constant(lo, hi):
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
            fractions.append(f"{states[zero]}/{states[index]}")
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


#: Parity on two inputs: consume the unique phase primes 3/7 once, depositing
#: 5 for each.  Cancel paired ones, then move the remaining 5 onto answer 2.
_PARITY_TWO = "21 $/3 $/7 1/25 2/5"
_PARITY_PAIR = ("1", "5")
#: Width < 4 cannot hold "1/25", so it takes the binary form.
_PARITY_BINARY = "21 $/3 $/7 1/4"


def fractran(truth_table: str, width: int | None = None) -> str:
    """Return a template; narrow tables give the root the smallest state prime.

    Halts at 1 or 2 for zero or one; input-prime exponents are filled by ``PAIR``.
    """
    from esolangs.tools.wrap import wrap_program

    n = _validate_truth_table(truth_table)
    program = _plain(truth_table, n)
    if width is None:
        return program
    floor = _widest(program)
    if floor > width:
        narrow = _plain(truth_table, n, small_root=True)
        if _widest(narrow) < floor:
            program = narrow
    if (
        n == 2
        and _widest(program) > width
        and all(int(bit) == row.bit_count() % 2 for row, bit in enumerate(truth_table))
    ):
        program = _PARITY_BINARY if width < 4 else _PARITY_TWO
    return wrap_program(program, "fractran", width)


def fractran_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return parity numerator setters only for the exact two-phase program."""
    pair = PAIR
    if n == 2:
        if template.split() == _PARITY_TWO.split():
            pair = _PARITY_PAIR
        elif template.split() == _PARITY_BINARY.split():
            pair = ("1", "2")
    return (pair,) * n
