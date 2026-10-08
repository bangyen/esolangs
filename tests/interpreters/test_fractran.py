"""Execution tests for the FRACTRAN interpreter."""

# ruff: noqa: SLF001

import random
import re

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _choose, _Machine, _parse, run
from esolangs.interpreters.other.fractran import index as fractran_index
from tests.interpreters.runner import run_program

#: Conway's PRIMEGAME.  The powers of two it passes through are the primes.
PRIMEGAME = (
    "17/91 78/85 19/51 23/38 29/33 77/29 95/23 77/19 1/17 11/13 13/11 15/14 15/2 55/1"
)


def test_the_two_fraction_adder() -> None:
    """``3/2`` moves every 2 in the value over to a 3: 2**3 * 3**4 -> 3**7."""
    assert run_program(run, "2^3*3^4 3/2") == str(3**7)


def test_a_value_no_fraction_divides_is_printed_at_once() -> None:
    assert run_program(run, "7") == "7"


def test_prime_power_notation_is_only_notation() -> None:
    start, fractions, _offsets = _parse("2^3*5 7/2")
    assert start == 40
    assert fractions == ((7, 2),)


def test_the_first_matching_fraction_wins() -> None:
    """Both divide 6, so the order decides -- the language's only control flow."""
    first = _Machine("6 5/2 7/3", ScriptedIO(""))
    first.step()
    assert first.value == 15
    second = _Machine("6 7/3 5/2", ScriptedIO(""))
    second.step()
    assert second.value == 14


def test_primegame_passes_through_the_primes() -> None:
    machine = _Machine("2 " + PRIMEGAME, ScriptedIO(""))
    seen = []
    for _ in range(60_000):
        if machine.halted:
            break
        value, power = machine.value, 0
        while value % 2 == 0:
            value //= 2
            power += 1
        if value == 1 and power > 1:
            seen.append(power)
        machine.step()
    assert seen[:8] == [2, 3, 5, 7, 11, 13, 17, 19]


@pytest.mark.parametrize(
    ("program", "message"),
    [
        ("", "needs a starting value"),
        ("2 3/x", "not a FRACTRAN number or power"),
        ("0 3/2", "must be positive"),
        ("2 3/0", "divides by zero"),
    ],
)
def test_a_malformed_program_is_refused(program: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        run_program(run, program)


def test_the_pointer_is_the_offset_of_the_fraction_about_to_fire() -> None:
    source = "6 5/2 7/3"
    machine = _Machine(source, ScriptedIO(""))
    assert machine.ip == source.index("5/2")
    machine.step()
    assert machine.ip == source.index("7/3")


def test_the_final_print_is_its_own_step() -> None:
    """``halted`` stays false until the value has been printed."""
    machine = _Machine("7", ScriptedIO(""))
    assert not machine.halted
    assert _choose(machine.value, machine.fractions) is None
    machine.step()
    assert machine.halted
    assert machine.ip is None


def test_a_non_positive_numerator_is_refused() -> None:
    with pytest.raises(ValueError, match="is not positive"):
        run_program(run, "5 0/3")


@pytest.mark.medium
def test_incremental_guards_match_literal_threshold_crossings() -> None:
    rng = random.Random(20261007)
    primes = (2, 3, 5, 7, 11)

    def product() -> str:
        terms = [f"{prime}^{rng.randrange(4)}" for prime in primes]
        return "*".join(terms)

    for _ in range(200):
        source = " ".join([product(), *(f"{product()}/{product()}" for _ in range(12))])
        machine = _Machine(source, ScriptedIO(""))
        assert machine._cursor is not None
        value, fractions, _offsets = _parse(source)
        for _ in range(64):
            selected = _choose(value, fractions)
            assert machine._next() == selected
            # Repeated reads must not change eligibility or charge inspections.
            inspections = machine.inspections
            assert machine._next() == selected
            assert machine.inspections == inspections
            machine.step()
            if selected is None:
                assert machine.halted
                break
            numerator, denominator = fractions[selected]
            value = value * numerator // denominator
            assert machine.value == value


def test_indexed_transitions_do_not_materialize_factor_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    machine = _Machine("2^20*3^20 5/2 7/3 1/5 1/7", ScriptedIO(""))
    assert machine._cursor is not None

    def forbidden(_machine: _Machine) -> None:
        pytest.fail("ordinary indexed execution copied the canonical factor snapshot")

    monkeypatch.setattr(_Machine, "_factors", property(forbidden))
    while not machine.halted:
        machine.step()
    assert machine.value == 1
    assert machine._cursor.factor_updates == 120


def test_least_prime_sieve_factors_match_literal_arithmetic() -> None:
    for value in range(1, 513):
        # Unit factors admit bases through 512 without changing the integer.
        start = "*".join([str(value), *(["1"] * 22)])
        source = f"{start} {value}/2 {value}/3 {value}/5"
        index = fractran_index.compile_index(source)
        assert index is not None
        initial, fractions, _offsets = _parse(source)
        assert fractran_index.integer(index.initial) == initial
        assert (
            tuple(
                (fractran_index.integer(head), fractran_index.integer(tail))
                for head, tail in index.literal
            )
            == fractions
        )


def test_loader_sieve_uses_actual_bases_and_keeps_sparse_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = fractran_index._least_primes
    limits = []

    def record(limit: int) -> list[int]:
        limits.append(limit)
        return original(limit)

    monkeypatch.setattr(fractran_index, "_least_primes", record)
    dense = "*".join(["2"] * 100) + " 3/2 1/3"
    machine = _Machine(dense, ScriptedIO(""))
    assert machine._index is not None
    assert limits == [3]
    assert run_program(run, "239 1/239") == "1"
    assert limits == [3]
    assert fractran_index.compile_index("257 1/257") is None
    assert limits == [3]


def test_sieve_products_have_linear_fractional_bit_weight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pairs: list[tuple[int, int]] = []

    class Tracked(int):
        def __mul__(self, other: int) -> int:
            pairs.append((int(self), int(other)))
            return int(self) * int(other)

    def tracked_range(*args: int):
        return (Tracked(value) for value in range(*args))

    monkeypatch.setattr(fractran_index, "range", tracked_range, raising=False)
    for bound in (0, 1, 2, 8, 64, 256, 1024):
        pairs.clear()
        least = fractran_index._least_primes(bound)
        products = []
        weight = 0
        for prime, candidate in pairs:
            assert prime <= least[candidate]
            if prime * candidate <= bound:
                products.append(prime * candidate)
            # Exact ceiling of bit_length(prime)**(2/3), without floats.
            amount = 1
            while amount**3 < prime.bit_length() ** 2:
                amount += 1
            weight += amount
        composites = {value for value in range(2, bound + 1) if least[value] != value}
        assert set(products) == composites
        assert len(products) == len(composites)
        assert weight <= 11 * bound
