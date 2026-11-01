"""Execute the generated DAG and check its reversible swap invariant."""

from fractions import Fraction
from itertools import product
from random import Random

import esolangs
from esolangs.languages.refractran.generator import _swap
from esolangs.languages.refractran.interpreter import _Machine
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


def test_tables_and_reference() -> None:
    """Swap invariants, all small tables and seeded larger tables, every row."""
    _check_controlled_swap()
    for n in (1, 2, 3):
        for value in range(2**2**n):
            table = format(value, f"0{2**n}b")
            assert evaluate_generated("REFRACTRAN", table) == table
    for n in (4, 5, 6):
        rng = Random(1847 + n)
        table = "".join(rng.choice("01") for _ in range(2**n))
        template = esolangs.generate("REFRACTRAN", table)
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
