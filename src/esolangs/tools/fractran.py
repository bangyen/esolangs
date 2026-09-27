"""FRACTRAN boolean program builder: a decision tree priced in primes.

The inputs are embedded as the exponents of ``n`` primes in the starting
value, since FRACTRAN has no input vocabulary at all, and the fractions walk a
decision tree.  Each internal node owns two fractions: the first divides by
the node's input prime and moves to the one-child, the second moves to the
zero-child, reachable only when the first does not divide -- FRACTRAN's own
first-match rule is the ``else``.  A leaf leaves ``2`` for a one and ``1`` for
a zero, which no fraction divides, so that value is where the run stops and
what it prints, in at most ``2n + 1`` steps: the cheapest execution here.

A folded leaf leaves the input primes below it unconsumed, and the trailing
``1/p`` fractions clear them.  They are last, so while any node prime remains
some earlier fraction always fires and they get their turn only at the end.

Output size is ``Theta(T log T)``, and the reason is the language's address
budget rather than this construction: fractions sharing a guard are dead after
the first, so ``m`` live ones cost ``m log m`` characters, and a prime costs
``log10 p`` additively however it is packed into a number.  Addressing ``T``
rows pays both, and this tree attains them -- ``3T + n - 2`` fractions over
``2T + n`` primes.  That bounds every construction which addresses rows, not
every program in the language: ``docs/proofs/fractran.md`` prices the routes
around it and pins its lemmas in ``tests/proofs/test_fractran_bound.py``.
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
    # 2 is the answer's prime, then one per input, then one per node: a row
    # surviving folding needs its own leaf prime, hence the address budget.
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
        # The one-child first: the zero-child is the else, by priority.
        fractions.append(f"{states[entry.one]}/{states[index] * inputs[entry.depth]}")
        fractions.append(f"{states[entry.zero]}/{states[index]}")
    fractions += [f"1/{prime}" for prime in inputs]
    return " ".join([start, *fractions])
