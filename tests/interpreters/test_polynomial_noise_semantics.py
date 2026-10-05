"""Exact root decoding with unrelated factors and repeated roots."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.polynomial import _Machine
from tests.interpreters.polynomial_parser import parse
from tests.interpreters.polynomial_reference import Reference


def multiply(left, right):
    result = [0] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            result[i + j] += a * b
    return result


def corpus():
    rng = random.Random(192583)
    for index in range(100):
        p = rng.choice((2, 3, 5, 7))
        operator = rng.randint(1, 8)
        coefficients = [-(p**operator), 1]
        real = rng.choice((-3, -1, 0, 1, 3))
        q = rng.choice((11, 13, 17))
        op = rng.randint(1, 6)
        coefficients = multiply(
            coefficients, [real * real + q ** (2 * op), -2 * real, 1]
        )
        for noise in rng.sample(
            ([1, 0, 1], [1, -1, 2], [-3, 2], [2, 0, 1]), rng.randint(1, 3)
        ):
            coefficients = multiply(coefficients, noise)
        if index % 5 == 0:
            coefficients = multiply(coefficients, [-(p**operator), 1])
        source = "f(x) = " + " ".join(
            f"{value:+d}" + (f"x^{degree}" if degree else "")
            for degree, value in reversed(list(enumerate(coefficients)))
            if value
        ).lstrip("+")
        yield source


@pytest.mark.medium
@pytest.mark.parametrize("source", list(corpus()))
def test_noisy_polynomial_state(source):
    instructions = parse(source)
    assert instructions
    reference = Reference([list(item) for item in instructions])
    port = ScriptedIO("")
    machine = _Machine(source, port)
    assert tuple(tuple(item) for item in machine.instructions) == instructions
    for _ in range(100):
        assert machine.snapshot() == (
            reference.cursor,
            reference.register,
            reference.offset,
            reference.reads,
            instructions,
        )
        assert (machine.ip, machine.memory, machine.stack, machine.halted) == (
            reference.cursor,
            [reference.register],
            [],
            reference.halted,
        )
        assert (port.position(), port.reads, port.getvalue()) == (
            reference.offset,
            reference.reads,
            reference.output,
        )
        if reference.halted:
            return
        expected_error = actual_error = None
        try:
            reference.step()
        except (ValueError, ZeroDivisionError, OverflowError) as error:
            expected_error = type(error)
        try:
            machine.step()
        except (ValueError, ZeroDivisionError, OverflowError) as error:
            actual_error = type(error)
        assert actual_error == expected_error
        if expected_error:
            assert machine.snapshot() == (
                reference.cursor,
                reference.register,
                reference.offset,
                reference.reads,
                instructions,
            )
            assert (port.position(), port.reads, port.getvalue()) == (
                reference.offset,
                reference.reads,
                reference.output,
            )
            return
    raise AssertionError("noisy polynomial execution bound")
