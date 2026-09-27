"""The lemmas ``docs/proofs/fractran.md`` rests on, as executable checks.

That document proves a size wall for every FRACTRAN program that gives each
table row its own address, and argues that the routes around it cost either
digits or steps.  It is deliberately *not* a language lower bound: the
counting argument that gives Factor one provably cannot be imported, because
a fraction list's priority order is behaviour and is cheap.  So FRACTRAN's
audit row stays open, and what earns it its place is an obstruction --
a semantic model of the language that every construction has broken on.
These are that model, pinned where it runs.

Following :mod:`tests.proofs.test_negatives`: measurements belong in the
document, where a stale number reads as stale.  What is pinned here is what
*cannot* happen -- a shadowed fraction never firing, prime identity never
mattering, an exponent never being readable without steps.  Each of those
absences is load-bearing, and each turns false silently.  A failure here is
not a regression to revert but an opening: the bound it supports is back in
play, and the paragraph each test names is the one to go and read.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import product
from math import gcd

import pytest

from esolangs.interpreters.other.fractran import _choose, _parse
from esolangs.tools.fractran import PAIR, fractran
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs

#: A fraction list, as the interpreter holds it.
type _Fractions = tuple[tuple[int, int], ...]

_TABLES = ("01", "0110", "1101", "10010110", "00011101", "11101000")


def _bits(row: int, n: int) -> list[int]:
    """``row`` as ``n`` bits, most significant first."""
    return [(row >> (n - 1 - i)) & 1 for i in range(n)]


def _program(table: str, row: int) -> tuple[int, _Fractions]:
    """The generated program for ``table``, with ``row``'s bits filled in."""
    n = len(table).bit_length() - 1
    filled = fill_runs(fractran(table), TEMPLATE_CHAR, [PAIR] * n, _bits(row, n))
    start, fractions, _offsets = _parse(filled)
    return start, fractions


def _trace(start: int, fractions: _Fractions) -> tuple[Counter[int], int]:
    """Run to a halt, returning the firing counts and the value it ends on."""
    value, fired = start, Counter[int]()
    while (index := _choose(value, fractions)) is not None:
        numerator, denominator = fractions[index]
        value = value * numerator // denominator
        fired[index] += 1
    return fired, value


def _guard(numerator: int, denominator: int) -> int:
    """The integer that must divide the value, per Lemma 1."""
    return denominator // gcd(numerator, denominator)


def _factor(value: int) -> Counter[int]:
    """``value``'s prime factorisation, by trial division."""
    found: Counter[int] = Counter()
    rest, divisor = value, 2
    while divisor * divisor <= rest:
        while rest % divisor == 0:
            found[divisor] += 1
            rest //= divisor
        divisor += 1
    if rest > 1:
        found[rest] += 1
    return found


def _primes_of(start: int, fractions: _Fractions) -> list[int]:
    """Every prime the program's text spells -- the set ``S`` of Lemma 4."""
    found: set[int] = set()
    for value in (start, *(part for pair in fractions for part in pair)):
        found |= set(_factor(value))
    return sorted(found)


def _exponent(value: int, prime: int) -> int:
    """The exponent of ``prime`` in ``value``."""
    return _factor(value)[prime]


def test_a_shadowed_fraction_is_dead_code() -> None:
    """Lemma 2: an equal reduced guard later in the list can never fire.

    Exhaustive over the small pairs, which is what makes Corollary 3 --
    distinct guards, hence distinct tokens, hence Theorem 7 -- safe to state
    for the live fractions only.  The mirror half matters too: sharing a
    *raw* denominator is not sharing a guard, so the reduction in Lemma 1 is
    doing real work and cannot be dropped.
    """
    shadowed = live = 0
    for num_a, den_a, num_b, den_b in product(range(1, 7), repeat=4):
        if _guard(num_a, den_a) != _guard(num_b, den_b):
            continue
        fractions = ((num_a, den_a), (num_b, den_b))
        fires = any(_choose(start, fractions) == 1 for start in range(1, 500))
        shadowed += not fires
        live += fires
    assert live == 0, "a fraction with an equal earlier guard fired"
    assert shadowed > 0, "the sweep found no shadowed pairs to check"

    sharing = [
        ((num_a, den_a), (num_b, den_b))
        for num_a, den_a, num_b, den_b in product(range(1, 9), repeat=4)
        if den_a == den_b and _guard(num_a, den_a) != _guard(num_b, den_b)
    ]
    both = [
        pair
        for pair in sharing
        if any(_choose(start, pair) == 1 for start in range(1, 500))
    ]
    assert both, "a shared raw denominator never left the second fraction live"


def test_the_run_cannot_see_a_prime_the_text_does_not_spell() -> None:
    """Lemma 4: primes outside ``S`` are invariant and change no decision.

    The encoding consequence is the load-bearing one: a large literal factor
    carries its digits to a reader and nothing to the machine, so a table
    cannot be stored as a number.  If a step ever branched on one, the
    "What a program can read" section is wrong and the packing routes reopen.
    """
    for table in _TABLES:
        n = len(table).bit_length() - 1
        for row in range(2**n):
            start, fractions = _program(table, row)
            outside = 10**9 + 7
            assert outside not in _primes_of(start, fractions)
            plain, halted = _trace(start, fractions)
            scaled, halted_scaled = _trace(start * outside, fractions)
            assert scaled == plain, (table, row)
            assert halted_scaled == halted * outside, (table, row)


def test_relabelling_the_primes_preserves_the_whole_run() -> None:
    """Lemma 5: only a prime's rank and role are readable, never its value.

    Every prime in the program is mapped to a fresh, larger one, order
    preserved, and the run is required to fire the same fractions the same
    number of times and to answer in the image of the answer prime.  This is
    why Theorem 8 may price a prime by its rank: nothing else about it is
    usable.
    """
    for table in _TABLES:
        n = len(table).bit_length() - 1
        for row in range(2**n):
            start, fractions = _program(table, row)
            primes = _primes_of(start, fractions)
            targets = _next_primes(after=max(primes), count=len(primes))
            mapping = dict(zip(primes, targets, strict=True))
            moved_start = _relabel(start, mapping)
            moved = tuple(
                (_relabel(num, mapping), _relabel(den, mapping))
                for num, den in fractions
            )
            plain, halted = _trace(start, fractions)
            fired, halted_moved = _trace(moved_start, moved)
            assert fired == plain, (table, row)
            assert halted in (1, 2), (table, row)
            assert halted_moved == mapping[2] ** (halted - 1), (table, row)


def _next_primes(after: int, count: int) -> list[int]:
    """The first ``count`` primes strictly above ``after``."""
    found: list[int] = []
    candidate = after + 1
    while len(found) < count:
        if all(candidate % divisor for divisor in range(2, int(candidate**0.5) + 1)):
            found.append(candidate)
        candidate += 1
    return found


def _relabel(value: int, mapping: dict[int, int]) -> int:
    """``value`` with each prime replaced by its image."""
    moved = 1
    for prime, power in _factor(value).items():
        moved *= mapping[prime] ** power
    return moved


def test_the_answer_is_a_linear_form_in_the_firing_counts() -> None:
    """Theorem 12: ``e_p`` of the halt value is linear in the firing counts.

    A one-line identity with a long consequence -- Corollary 13, that
    per-level shared machinery computes only dictators, which is why every
    construction ends up spending a fraction per distinguished prefix and
    paying Theorem 7.
    """
    for table in _TABLES:
        n = len(table).bit_length() - 1
        for row in range(2**n):
            start, fractions = _program(table, row)
            weights = [_exponent(num, 2) - _exponent(den, 2) for num, den in fractions]
            fired, halted = _trace(start, fractions)
            predicted = _exponent(start, 2) + sum(
                count * weights[index] for index, count in fired.items()
            )
            assert halted in (1, 2), (table, row)
            assert predicted == _exponent(halted, 2), (table, row)
            assert halted == (2 if table[row] == "1" else 1), (table, row)


@pytest.mark.parametrize("n", range(1, 5))
def test_an_integer_affine_form_in_zero_one_is_a_dictator(n: int) -> None:
    """Corollary 13's algebra: the escape that shared machinery would need.

    Theorem 12 makes a per-level trace's answer an integer affine form in the
    bits.  Requiring that form to land in ``{0, 1}`` everywhere leaves only
    the constants and the (negated) dictators, so an arbitrary table forces
    either a fraction per distinguished prefix or a loop.
    """
    rows = list(product((0, 1), repeat=n))
    for const in range(-2, 3):
        for weights in product(range(-2, 3), repeat=n):
            values = {
                const + sum(w * x for w, x in zip(weights, row, strict=True))
                for row in rows
            }
            if not values <= {0, 1}:
                continue
            nonzero = [w for w in weights if w]
            assert len(nonzero) <= 1, (const, weights)
            assert not nonzero or nonzero[0] in (-1, 1), (const, weights)


def test_reading_a_big_exponent_costs_steps_not_characters() -> None:
    """Lemma 11: a cheap exponent literal is not cheap to read.

    This is the correction the document records.  Under plain fraction
    notation an exponent is paid in digits (Lemma 10), but this port parses
    ``p^e`` everywhere, so the literal costs ``log10 e`` and the *size* axis
    does not forbid packing a table into one exponent at all.  What forbids
    it is that each step shifts an exponent by a bounded amount, so the run
    has to traverse it: the text here stays 14 characters while the run grows
    with ``E``.  If this ever came apart, the size claim would need the
    clock hypothesis removed -- or would be false.
    """
    widths = set()
    for power in (16, 32, 64, 128, 256):
        code = f"2^{power} 3/2^2 1/3"
        start, fractions, _offsets = _parse(code)
        fired, halted = _trace(start, fractions)
        assert sum(fired.values()) == power, code
        assert halted == 1, code
        widths.add(len(code))
    assert max(widths) - min(widths) <= 1, "the text grew with the exponent"


def test_the_tree_pays_the_address_budget_it_is_priced_by() -> None:
    """Corollary 9 is attained: a guard and two primes per row, all distinct.

    The exact counts, not a fitted growth: the unfoldable table gives
    ``m = 3T + n - 2`` fractions over ``k = 2T + n`` primes with pairwise
    distinct guards, so Theorems 7 and 8 both bind on the shipped generator
    and the ``Theta(T log T)`` it measures is the budget rather than slack.
    """
    for n in range(2, 8):
        size = 1 << n
        parity = "".join(str(bin(row).count("1") & 1) for row in range(size))
        start, fractions = _program(parity, 0)
        guards = [_guard(num, den) for num, den in fractions]
        assert len(fractions) == 3 * size + n - 2, n
        assert len(set(guards)) == len(guards), n
        assert len(_primes_of(start, fractions)) == 2 * size + n, n
        assert len(fractran(parity)) >= math.log10(math.factorial(len(fractions)))


def test_priority_order_is_the_channel_the_wall_does_not_cover() -> None:
    """ "What is not proved": order carries a bit per character, undamped.

    `m` fractions carry `log2(m!)` bits of priority, and Theorem 7 prices
    them at `m log_c m` characters.  The arithmetic pinned here is the one
    that keeps the row open: enough order to name any table is already
    bought at `Theta(T)` characters, so no counting argument can reach
    `Omega(T log T)`, and the open question is whether a decoder exists.
    """
    alphabet = 14
    for n in range(8, 14):
        size = 1 << n
        needed = next(
            m for m in range(2, 4 * size) if math.log2(math.factorial(m)) >= size
        )
        cost = needed * math.log(needed, alphabet)
        assert needed < size, (n, needed)
        assert cost < 2 * size, (n, cost)
        assert size / math.log2(alphabet) <= cost, (n, cost)
