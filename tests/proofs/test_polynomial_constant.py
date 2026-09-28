"""Executable controls for the explicit Polynomial constant."""

import itertools
import math
from fractions import Fraction

import pytest

from esolangs.interpreters.register_based.polynomial import (
    _advance,
    _bracket_pairs,
    sanitize_terms,
)
from esolangs.tools._polynomial import format_coeffs, multiply, primes
from esolangs.tools.polynomial import _polynomial_decode_key
from tests.tools.boolean_runners import run_polynomial


def test_symmetric_remainders_have_independent_zero_positions() -> None:
    """The two expensive-gap targets in ``lem:evencount`` need two choices."""

    def first_zeros(moduli: list[int]) -> tuple[int, int]:
        values = [48, 49]
        found = [0, 0]
        for position, modulus in enumerate(moduli, 1):
            values = [(value % -modulus) % modulus for value in values]
            for bit, value in enumerate(values):
                if not value and not found[bit]:
                    found[bit] = position
        return found[0], found[1]

    for first in range(1, 5):
        for second in range(first + 1, 6):
            moduli = [53] * 5
            moduli[first - 1], moduli[second - 1] = 48, 1
            assert first_zeros(moduli) == (first, second)

            moduli[first - 1], moduli[second - 1] = 49, 48
            assert first_zeros(moduli) == (second, first)


def test_maximal_width_reaches_half_the_asymptotic_scale() -> None:
    """The chosen level in ``lem:maximal-width`` gives ``N_n >= T/(2n)``."""
    for n in range(2, 33):
        j = max(2, math.ceil(math.log2(n)))
        residuals = 2 ** (n - j)
        first_essential = 2 ** (2**j) - 2 ** (2 ** (j - 1)) - 2
        assert min(residuals, first_essential) * 2 * n >= 2**n


def test_decoder_slack_cannot_lower_the_effective_profile() -> None:
    """The relaxed operand/state trade after ``lem:effprofile`` bottoms at zero."""
    baseline = Fraction(325, 8)
    for numerator in range(51):
        delta = Fraction(numerator, 100)
        relaxed = (baseline - 4 * delta) / (1 - delta) ** 2
        assert relaxed >= baseline


def test_one_instruction_split_has_no_cheaper_opcode() -> None:
    """An exhaustive control pins the local split's minimal root profile."""
    baseline = [1, 1, 1, 4]
    test_exponent = {-1: 3, 0: 4, 1: 1}
    separating: list[tuple[int, int, list[int]]] = []

    for opcode in range(1, 7):
        for operand in range(-100, 101):
            if not operand:
                continue
            if opcode == 1:
                values = [register + operand for register in (48, 49)]
            elif opcode == 2:
                values = [register - operand for register in (48, 49)]
            elif opcode == 3:
                values = [register * operand for register in (48, 49)]
            elif opcode == 4:
                values = [register // operand for register in (48, 49)]
            elif opcode == 5:
                values = [register % operand for register in (48, 49)]
            else:
                values = [Fraction(register) ** operand for register in (48, 49)]

            signs = [0 if value == 0 else 1 if value > 0 else -1 for value in values]
            if signs[0] == signs[1]:
                continue
            profile = sorted(
                [opcode, opcode, test_exponent[signs[0]], test_exponent[signs[1]]]
            )
            assert all(
                actual >= best for actual, best in zip(profile, baseline, strict=True)
            )
            separating.append((opcode, operand, profile))

    assert (1, -48, baseline) in separating


def _even_source(table: str) -> tuple[str, list[list[int]], list[int]]:
    n = (len(table) - 1).bit_length()
    instructions: list[list[int]] = []

    def build(prefix: int, depth: int) -> None:
        if depth == n:
            value = int(table[prefix])
            instructions.extend([[0, 2], [-8, 3], [8, 3]])
            shift = 16 - value
            instructions.extend([[-shift, 1], [0, 1], [shift, 1]])
            return
        instructions.extend([[-48, 2], [0, 2], [48, 2], [1]])
        build(2 * prefix + 1, depth + 1)
        instructions.extend([[2], [4]])
        build(2 * prefix, depth + 1)
        instructions.append([2])

    build(0, 0)
    groups: list[list[list[int]]] = []
    for instruction in instructions:
        if groups and _polynomial_decode_key(groups[-1][-1]) <= _polynomial_decode_key(
            instruction
        ):
            groups[-1].append(instruction)
        else:
            groups.append([instruction])
    factors: list[list[int]] = []
    for group, prime in zip(groups, primes(len(groups)), strict=True):
        for instruction in group:
            if len(instruction) == 1:
                root = prime ** instruction[0]
                factors.append([1, 0, -(root * root)])
            else:
                operand, opcode = instruction
                factors.append(
                    [1, -2 * operand, operand * operand + prime ** (2 * opcode)]
                )
    coefficients = [1]
    for factor in factors:
        coefficients = multiply(coefficients, factor)
    return format_coeffs(coefficients), instructions, coefficients


def _execute(instructions: list[list[int]], bits: str) -> str:
    pairs = _bracket_pairs(instructions)
    state, position, output = (0, 0), 0, ""
    while state[1] < len(instructions):
        instruction = instructions[state[1]]
        byte = None
        if instruction[1:] == [2] and instruction[0] == 0:
            byte = 48 + int(bits[position]) if position < len(bits) else -1
            position += 1
        state, printed = _advance(state, instructions, byte, pairs)
        output += printed or ""
    return output


# 3.3s: the only test factoring and running the symmetric construction; it
# pins both source parities and exhausts the two-input instruction programs.
@pytest.mark.medium
def test_even_sources_compute_every_two_input_table() -> None:
    """The symmetric decision tree after ``lem:symruns`` is an even source."""
    for bits in itertools.product("01", repeat=4):
        table = "".join(bits)
        program, instructions, coefficients = _even_source(table)
        assert all(exponent % 2 == 0 for exponent in sanitize_terms(program))
        output = "".join(_execute(instructions, f"{row:02b}") for row in range(4))
        assert output == table
        if table == "0110":
            actual = "".join(
                run_polynomial(program, list(f"{row:02b}")) for row in range(4)
            )
            assert actual == table
            odd = format_coeffs(multiply(coefficients, [1, 0]))
            if odd.endswith("x"):
                odd += "^1"
            assert all(
                exponent % 2 == 1
                for exponent, coefficient in sanitize_terms(odd).items()
                if coefficient
            )
            odd_actual = "".join(
                run_polynomial(odd, list(f"{row:02b}")) for row in range(4)
            )
            assert odd_actual == table
