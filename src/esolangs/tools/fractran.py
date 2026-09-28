"""FRACTRAN boolean program builder: a block of the table in one exponent.

The inputs are embedded as the exponents of ``n`` primes in the starting
value, since FRACTRAN has no input vocabulary at all.  A decision tree over
the high inputs walks to a *block* of consecutive entries -- a node owns two
fractions, the first dividing by its input prime, the second reachable only
when that one does not divide, which is FRACTRAN's first-match rule as the
``else`` -- and the leaf loads its whole block as a single exponent.  A fixed
decoder of twelve fractions then shifts that exponent right by the offset
the remaining inputs spell in unary, and answers with the parity of what is
left: ``2`` for a one and ``1`` for a zero, which no fraction divides, so that
value is where the run stops and what it prints.  A folded span answers
without decoding; the trailing ``1/p`` fractions clear what it left unread.

Output size is ``Theta(T)``.  Addressing every row would not be: guards are
distinct, so ``m`` fractions cost ``m log m`` characters and ``k`` primes cost
``k log10 k``, and a row per address pays ``Theta(T log T)``.  This pays that
budget for ``3T / w`` addresses instead, and buys the difference on the clock
-- a block in an exponent has to be traversed, so a run is ``O(2**w)`` steps.
Below about ``n = 4`` the decoder costs more than it saves.
``docs/proofs/fractran.md`` proves both ends and the floor they sit above.
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

#: Primes the decoder reserves, ahead of the inputs and the tree's states:
#: the answer's 2, the two the block shuttles between, the offset counter,
#: and six to hold a loop's phase.
_CONTROL = 10


@dataclass(frozen=True)
class _Leaf:
    """A folded subtable: the answer, and the level it stops reading at."""

    answer: str
    depth: int


@dataclass(frozen=True)
class _Block:
    """An unfolded leaf: the ``w`` entries it loads, as one integer."""

    chunk: int


@dataclass(frozen=True)
class _Node:
    """An internal node: the input it reads, and its children's indices."""

    depth: int
    zero: int
    one: int


def _plan(n: int) -> tuple[int, int]:
    """Return ``v`` and how many blocks take the wider width ``2**(v + 1)``.

    Linearity needs only ``w = Omega(n)`` and a block costs ``O(2**w)`` steps
    to read, so the narrowest qualifying width wins: ``w`` near ``n / 3``.
    A power of two is too coarse a knob -- characters an entry would saw
    where ``w`` doubled -- so both widths are mixed to average the target,
    and covering a fraction ``x`` with the wider ones leaves
    ``(T / w)(1 - x / 2)`` blocks, which fixes ``x``.
    """
    triple = max(9, n)
    v = max(1, min(n, (triple // 3).bit_length() - 1))
    if v >= n:
        return v, 0
    # ``x = 1 - 2**v / target`` with ``target = triple / 3``, in integers.
    wide = (1 << n) * (triple - 3 * (1 << v)) // (triple << v)
    return v, min(wide, 1 << (n - v - 1))


def _primes(count: int) -> list[int]:
    """Return the first ``count`` primes, 2 first."""
    stream = (
        prime
        for _start, _stop, segment in prime_segments(_PRIME_CHUNK)
        for prime in segment
    )
    return list(islice(stream, count))


def _tree(truth_table: str, n: int, v: int, wide: int) -> list[_Leaf | _Block | _Node]:
    """Return the block tree, post-order, root last.

    ``wide`` blocks stop a level above the rest, holding twice as many
    entries; which ones is arbitrary, only how many.
    """
    constant = constant_span_test(truth_table)
    nodes: list[_Leaf | _Block | _Node] = []
    budget = [wide]

    def block(lo: int, hi: int) -> int:
        # Low entry first, so the offset is the exponent's own shift.
        nodes.append(_Block(sum(int(truth_table[lo + i]) << i for i in range(hi - lo))))
        return len(nodes) - 1

    def walk(depth: int, lo: int, hi: int) -> int:
        if constant(lo, hi):
            nodes.append(_Leaf(truth_table[lo], depth))
        elif depth == n - v:
            return block(lo, hi)
        elif depth == n - v - 1 and budget[0] > 0:
            budget[0] -= 1
            return block(lo, hi)
        else:
            mid = (lo + hi) // 2
            zero = walk(depth + 1, lo, mid)
            one = walk(depth + 1, mid, hi)
            nodes.append(_Node(depth, zero, one))
        return len(nodes) - 1

    walk(0, 0, len(truth_table))
    return nodes


def _decoder(control: list[int]) -> list[str]:
    """Return the twelve fractions that read one bit out of a block.

    Each loop alternates between two phase primes, because a fraction holding
    its own phase prime in numerator and denominator alike would cancel it
    out of the guard the interpreter tests, and fire everywhere.  The last
    two need no phase: every earlier state holds a tree state or a phase
    prime whose unguarded fraction comes first.
    """
    carry, work, count = control[1:4]
    ready, halve, shift, back, move, cycle = control[4:]
    return [
        # A shift still to make?  Spend one unit of the offset counter.
        f"{shift}/{ready * count}",
        # Halve, by moving two of the carry prime into one of the work prime.
        f"{halve}*{work}/{shift}*{carry}^2",
        f"{shift}/{halve}",
        f"{back}/{shift}",
        # Whatever the halving shifted out is not the answer.
        f"{move}/{back}*{carry}",
        f"{move}/{back}",
        # Move the halved block back, for the next shift to read.
        f"{cycle}*{carry}/{move}*{work}",
        f"{move}/{cycle}",
        f"{ready}/{move}",
        # The counter is spent: the answer is the low bit of what is left,
        # found by casting out pairs.
        f"1/{ready}",
        f"1/{carry}^2",
        f"2/{carry}",
    ]


def _power(prime: int, exponent: int) -> str:
    """Return ``prime^exponent``, or the bare prime for an exponent of 1."""
    return f"{prime}^{exponent}" if exponent > 1 else str(prime)


def fractran(truth_table: str) -> str:
    """Return a FRACTRAN template computing ``truth_table``.

    Each run of :data:`TEMPLATE_CHAR` is the exponent of one input's prime,
    filled with :data:`PAIR`; the instantiated program prints ``2`` where the
    table says one and ``1`` where it says zero.
    """
    n = _validate_truth_table(truth_table)
    v, wide = _plan(n)
    nodes = _tree(truth_table, n, v, wide)
    primes = _primes(_CONTROL + n + len(nodes))
    control = primes[:_CONTROL]
    carry, count, ready = control[1], control[3], control[4]
    inputs = primes[_CONTROL : _CONTROL + n]
    states = primes[_CONTROL + n :]

    fractions: list[str] = []
    for index, entry in enumerate(nodes):
        if isinstance(entry, _Leaf):
            fractions.append(f"{2 if entry.answer == '1' else 1}/{states[index]}")
        elif isinstance(entry, _Block):
            load = (
                f"{_power(carry, entry.chunk)}*{ready}" if entry.chunk else f"{ready}"
            )
            fractions.append(f"{load}/{states[index]}")
        else:
            # The one-child first: the zero-child is the else, by priority.
            one, zero = entry.one, entry.zero
            fractions.append(f"{states[one]}/{states[index] * inputs[entry.depth]}")
            fractions.append(f"{states[zero]}/{states[index]}")
    # The offset, in unary: one fraction per input the tree did not read.
    # They sit *after* the tree and before the decoder, which is what makes
    # them safe -- a descending tree always has a fraction of its own to
    # fire, so these get their turn only once a block is loaded.  The widest
    # weight belongs to the level a wide block skipped; under a narrow one
    # that prime is already gone, so the two widths need no marker.
    first = n - v - 1 if wide and v < n else n - v
    fractions += [
        f"{_power(count, 1 << (n - 1 - level))}/{inputs[level]}"
        for level in range(first, n)
    ]
    fractions += _decoder(control)
    # A folded answer leaves the tree's inputs from its level down unread,
    # and an offset that no block asked for; a block's path spends both.
    shallowest = min((e.depth for e in nodes if isinstance(e, _Leaf)), default=n)
    if shallowest < n:
        fractions += [f"1/{prime}" for prime in (*inputs[shallowest:first], count)]

    start = "*".join(
        [str(states[-1])] + [f"{prime}^{_FRACTRAN_INPUT}" for prime in inputs]
    )
    return " ".join([start, *fractions])
