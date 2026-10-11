"""The lemmas ``docs/proofs/fractran.md`` rests on, as executable checks."""

from __future__ import annotations

import math
from collections import Counter
from itertools import product
from math import gcd

import pytest

from esolangs.interpreters.other.fractran import _choose, _parse
from esolangs.tools.fractran import PAIR, fractran
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.proofs.deep.fractran import row_addressed, rows, spelled
from tests.support.witness_tables import row_bits

#: A fraction list, as the interpreter holds it.
type _Fractions = tuple[tuple[int, int], ...]

_TABLES = ("01", "0110", "1101", "10010110", "00011101", "11101000")


def _program(table: str, row: int) -> tuple[int, _Fractions]:
    """The generated program for ``table``, with ``row``'s bits filled in."""
    n = len(table).bit_length() - 1
    text = row_addressed(table)
    filled = fill_runs(text, TEMPLATE_CHAR, [PAIR] * n, row_bits(row, n))
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
    """Lemma 2: an equal reduced guard later in the list can never fire."""
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
    """Lemma 4: primes outside ``S`` are invariant and change no decision."""
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
    """Lemma 5: only a prime's rank and role are readable, never its value."""
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
    """Theorem 12: ``e_p`` of the halt value is linear in the firing counts."""
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
    """Corollary 13's algebra: the escape that shared machinery would need."""
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
    """Lemma 11: a cheap exponent literal is not cheap to read."""
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
    """Corollary 9 is attained: a guard and two primes per row, all distinct."""
    for n in range(2, 8):
        size = 1 << n
        parity = "".join(str(bin(row).count("1") & 1) for row in range(size))
        start, fractions = _program(parity, 0)
        guards = [_guard(num, den) for num, den in fractions]
        assert len(fractions) == 3 * size + n - 2, n
        assert len(set(guards)) == len(guards), n
        assert len(_primes_of(start, fractions)) == 2 * size + n, n
        assert len(row_addressed(parity)) >= math.log10(math.factorial(len(fractions)))


def _pseudo_table(n: int) -> str:
    """A table with no structure for the tree to fold, made the same way twice."""
    state = 0x9E3779B9
    bits = []
    for _ in range(1 << n):
        state = (state * 1103515245 + 12345) & 0xFFFFFFFF
        bits.append(str((state >> 16) & 1))
    return "".join(bits)


def test_the_shipped_builder_answers_every_row_without_addressing_one() -> None:
    """Theorem 15: a program does not have to give a row an address."""
    table = _pseudo_table(8)
    worst, _widest = rows(fractran(table), table)
    assert worst <= 8 + 1, "a run fired more than a fraction a level and a leaf"
    assert len(spelled(fractran(table))) < len(table) // 2


def test_sharing_pays_the_address_budget_rather_than_escaping_it() -> None:
    """Corollary 9 covers the shared program too, and does not bind."""
    table = _pseudo_table(12)
    template = fractran(table)
    assert len(template.split()) - 1 < len(table) // 2
    assert len(spelled(template)) < len(table) // 4
    assert len(template) < 5 * len(table)
    assert len(row_addressed(table)) > 5 * len(template)


def test_priority_order_is_a_channel_no_counting_argument_can_close() -> None:
    """ "Size-time frontier": order carries a bit per character, undamped."""
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


def _bounded_scan(
    start: int, fractions: _Fractions, limit: int = 32
) -> tuple[int, int, int] | None:
    """Return halt value, inspections, and largest materialized integer."""
    value, probes, largest = start, 0, start
    seen: set[int] = set()
    for _ in range(limit):
        if value in seen:
            return None
        seen.add(value)
        for numerator, denominator in fractions:
            probes += 1
            multiplied = value * numerator
            largest = max(largest, multiplied)
            if multiplied % denominator == 0:
                value = multiplied // denominator
                break
        else:
            return value, probes, largest
    return None


def test_scan_counting_bound_includes_the_zero_fraction_case() -> None:
    """Finite encodings cover order, unreduced fractions, and input labels."""
    # Width two allows integers 1, 2, 3. Overcount input bases as arbitrary
    # integers: both orders and non-primes must be covered by the bound.
    width, inspections, n = 2, 1, 1
    values = range(1, 1 << width)
    behaviours: set[tuple[int, ...]] = set()
    descriptions = 0
    for fixed, base in product(values, repeat=2):
        for fractions in [(), *((pair,) for pair in product(values, repeat=2))]:
            descriptions += 1
            starts = (fixed, fixed * base)
            traces = [_bounded_scan(start, fractions) for start in starts]
            if any(trace is None for trace in traces):
                continue
            total = [trace for trace in traces if trace is not None]
            if any(
                trace[0] not in (1, 2)
                or trace[1] > inspections
                or trace[2].bit_length() > width
                for trace in total
            ):
                continue
            behaviours.add(tuple(trace[0] for trace in total))
    bound = (inspections + 1) * (1 << ((2 * inspections + n + 1) * width))
    assert 0 < len(behaviours) <= descriptions <= bound
    assert (1, 2) in behaviours, "the projection control never executed"


@pytest.mark.medium
@pytest.mark.parametrize("bit", ["0", "1"])
def test_source_floor_is_worst_case_not_per_program(bit: str) -> None:
    # A 1,024-row constant table has a 134-character template, below the
    # counting floor for the hardest table; execute every row to pin this.
    table = bit * 1024
    template = fractran(table)
    assert set(template) <= set("0123456789/*^ $")
    assert TEMPLATE_CHAR in template
    assert len(template) < len(table) / math.log2(15) - 1
    for row in range(len(table)):
        code = fill_runs(template, TEMPLATE_CHAR, [PAIR] * 10, row_bits(row, 10))
        start, fractions, _offsets = _parse(code)
        _fired, halted = _trace(start, fractions)
        assert halted == (2 if bit == "1" else 1)
