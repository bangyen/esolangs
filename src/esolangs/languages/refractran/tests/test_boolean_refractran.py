"""Execute the generated DAG and check its reversible swap invariant."""

from fractions import Fraction
from itertools import product
from random import Random

import pytest

import esolangs
from esolangs.languages.refractran.generator import _swap
from esolangs.languages.refractran.interpreter import _Machine
from esolangs.runtime._evaluate import _evaluate
from esolangs.runtime.io import ScriptedIO
from tests.support.generator_support import evaluate_generated


def _rational_run(value: int, program: list[str]) -> int:
    """A spec-derived Fraction model, independent of the integer transition."""
    index, direction = 0, 1
    fractions = list(map(Fraction, program))
    for _ in range(10_000):
        if not 0 <= index < len(fractions):
            return value
        result = Fraction(value) * fractions[index] ** direction
        if result.denominator == 1:
            value = result.numerator
            direction = -direction
        index += direction
    raise AssertionError("reference step cap")


def _check_controlled_swap() -> None:
    """Every target/control assignment, with an omitted-reflection control."""
    for target, c0, c1 in product((0, 1), repeat=3):
        before = (3 if target else 2) * 19**c0 * 23**c1
        program = _swap(2, 3, (19, 23))
        expected = (3 if target ^ (c0 & c1) else 2) * 19**c0 * 23**c1
        machine = _Machine(f"{before} " + " ".join(program), ScriptedIO())
        for _ in range(16):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert machine.state.value == _rational_run(before, program) == expected

    assert _rational_run(2 * 19 * 23, _swap(2, 3, (19, 23))[:-1]) != 3 * 19 * 23

    for parity, bit in product((1, 2), (0, 1)):
        before = parity * 97 * 47**bit
        fuel, other = 97, 101
        fractions = []
        for factor in (5, 23, 31):
            fractions += _swap(fuel, other * factor, ())
            fuel, other = other, fuel
        expected = parity * fuel * 47**bit * 5 * 23 * 31
        machine = _Machine(str(before) + " " + " ".join(fractions), ScriptedIO())
        for _ in range(25):
            machine.step()
        assert machine.halted
        assert machine.state.value == _rational_run(before, fractions) == expected


@pytest.mark.medium
def test_tables_and_reference() -> None:
    """Swap invariants, all small tables and seeded larger tables, every row."""
    _check_constants()
    _check_controlled_swap()
    from esolangs.registry import LANGUAGES
    from scripts.tracediff import _cap_digits, _random_programs

    limit = LANGUAGES["REFRACTRAN"].fuzz_max_digits
    assert limit == 3
    programs = _random_programs([("2^3*3 3/2", "")], 300, limit)
    assert len(programs) == 300
    assert all(sum(c.isdigit() for c in code) <= 3 for code, _ in programs)
    bounded = _cap_digits("9^999999999999", limit)
    assert bounded == "9^99"
    assert esolangs.run("REFRACTRAN", bounded) == format(9**99, "b")
    for n in (1, 2, 3):
        for value in range(2**2**n):
            table = format(value, f"0{2**n}b")
            assert evaluate_generated("REFRACTRAN", table) == table
            balanced = esolangs.generate("REFRACTRAN", table, balance=True)
            assert _evaluate("REFRACTRAN", balanced, inputs=n) == table
    for n in (4, 5, 6):
        rng = Random(1847 + n)
        table = "".join(rng.choice("01") for _ in range(2**n))
        for options in ({}, {"balance": True}):
            template = esolangs.generate("REFRACTRAN", table, **options)
            for row, bits in enumerate(product((0, 1), repeat=n)):
                program = esolangs.instantiate("REFRACTRAN", template, bits)
                initial, *fractions = program.split()
                value = 1
                for term in initial.split("*"):
                    base, _, exponent = term.partition("^")
                    value *= int(base) ** int(exponent or "1")
                answer = _rational_run(value, fractions)
                output = esolangs.run("REFRACTRAN", program)
                assert int(output, 2) == answer
                assert esolangs.read_answer("REFRACTRAN", output) == table[row]


def _check_constants() -> None:
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("REFRACTRAN", bit * (1 << n), **options)
                assert template.count("$") == n
                for bits in ([0] * n, [1] * n):
                    source = esolangs.instantiate("REFRACTRAN", template, bits)
                    io = ScriptedIO("7")
                    machine = _Machine(source, io)
                    assert machine.state.value == (1 if bit == "1" else 2) * 3 ** sum(
                        bits
                    )
                    assert machine.state.value.bit_length() <= 2 * n + 1
                    assert not machine.fractions
                    assert not io.getvalue()
                    machine.step()
                    assert machine.halted
                    assert esolangs.read_answer("REFRACTRAN", io.getvalue()) == bit
                    assert io.reads == 0
                    assert io.input_char() == ord("7")
