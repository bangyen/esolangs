"""FRACTRAN boolean program builder: a decision tree priced in primes.

``fractran(truth_table)`` emits a template whose starting value carries the
inputs as the exponents of ``n`` primes -- FRACTRAN has no input vocabulary
at all, so the bits are embedded, one digit per input -- and whose fractions
walk a decision tree.  Each internal node owns two fractions: the first
divides by the node's input prime and moves to the one-child, the second
moves to the zero-child.  FRACTRAN's own first-match rule is the ``else``:
the second fraction is reachable only when the first does not divide.  A
leaf fraction consumes the node's prime and leaves ``2`` for a one and ``1``
for a zero, and no fraction divides either, so that value is where the run
stops and what it prints.

A subtable whose rows agree collapses to a leaf, which leaves the input
primes below it unconsumed.  The ``1/p`` fractions at the end of the list
clear them: they are last, so while any node prime is in the value some
earlier fraction always fires, and they get their turn only once the answer
is all that is left beside them.

A run is at most ``n + n + 1`` steps whatever the table says -- one per
level, one per cleared prime, and the leaf -- which is the cheapest
execution in the registry.

Output size is ``Theta(T log T)``, not linear, and the reason is the
language rather than this construction: see the FRACTRAN entry in
``docs/limitations.md``.  A FRACTRAN program can only ever test the
exponents of the primes its own text spells, so distinguishing ``T`` rows
costs ``T`` distinct primes, and the ``T``-th prime needs
``log10(T log T)`` digits to write down.  Packing several table entries into
one prime's exponent does not help: an exponent of ``2**k`` carries ``k``
bits and costs ``2**k`` in the value's digits.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice

from esolangs.factor_primes import prime_segments
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
)

#: How each input is set: the exponent of its prime in the starting value.
#: One digit wide, so the run is one :data:`TEMPLATE_CHAR`.
PAIR = ("0", "1")
_FRACTRAN_INPUT = TEMPLATE_CHAR * len(PAIR[0])

#: Segment width for the sieve; the primes wanted are a prefix of it.
_PRIME_CHUNK = 1 << 12

@dataclass(frozen=True)
class _Leaf:
    """A folded subtable: the answer, and nothing left to read."""

    answer: str


@dataclass(frozen=True)
class _Node:
    """An internal node: the input it reads, and its children's indices."""

    depth: int
    zero: int
    one: int


def _primes(count: int) -> list[int]:
    """Return the first ``count`` primes, 2 first."""
    stream = (
        prime
        for _start, _stop, segment in prime_segments(_PRIME_CHUNK)
        for prime in segment
    )
    return list(islice(stream, count))


def _tree(truth_table: str, n: int) -> list[_Leaf | _Node]:
    """Return the folded decision tree, post-order, root last."""
    constant = constant_span_test(truth_table)
    nodes: list[_Leaf | _Node] = []

    def walk(depth: int, lo: int, hi: int) -> int:
        if depth == n or constant(lo, hi):
            nodes.append(_Leaf(truth_table[lo]))
        else:
            mid = (lo + hi) // 2
            zero = walk(depth + 1, lo, mid)
            one = walk(depth + 1, mid, hi)
            nodes.append(_Node(depth, zero, one))
        return len(nodes) - 1

    walk(0, 0, len(truth_table))
    return nodes


def fractran(truth_table: str) -> str:
    """Return a FRACTRAN template computing ``truth_table``.

    The inputs are embedded: each run of :data:`TEMPLATE_CHAR` is the
    exponent of one input's prime, filled with :data:`PAIR`.  The
    instantiated program prints ``2`` where the table says one and ``1``
    where it says zero.
    """
    n = _validate_truth_table(truth_table)
    nodes = _tree(truth_table, n)
    # 2 is the answer's prime, then one prime per input, then one per node
    # of the tree -- every row that survives folding needs its own leaf
    # prime, which is the whole of why the emission is not linear.
    primes = _primes(1 + n + len(nodes))
    inputs = primes[1 : 1 + n]
    states = primes[1 + n :]

    start = "*".join(
        [str(states[-1])] + [f"{prime}^{_FRACTRAN_INPUT}" for prime in inputs]
    )
    fractions = []
    for index, entry in enumerate(nodes):
        if isinstance(entry, _Leaf):
            fractions.append(f"{2 if entry.answer == '1' else 1}/{states[index]}")
            continue
        # The one-child first: FRACTRAN tries them in order, so the
        # zero-child's fraction is reachable only when this one does not
        # divide -- that is the whole of the branch.
        fractions.append(
            f"{states[entry.one]}/{states[index] * inputs[entry.depth]}"
        )
        fractions.append(f"{states[entry.zero]}/{states[index]}")
    # Last, so a folded leaf's unread inputs are cleared only at the end.
    fractions += [f"1/{prime}" for prime in inputs]
    return " ".join([start, *fractions])
