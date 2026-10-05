"""Polynomial transitions checked against independent C-integer rules."""

import itertools

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.polynomial import (
    _advance,
    _bracket_pairs,
    _Machine,
)
from tests.interpreters.polynomial_encoding import encode
from tests.interpreters.polynomial_parser import parse
from tests.interpreters.polynomial_transition import transition


def outcome(function, state, program, byte):
    try:
        return function(state, program, byte), None
    except (ValueError, ZeroDivisionError) as error:
        return None, type(error).__name__


@pytest.mark.parametrize("register", range(-32, 33))
def test_arithmetic(register):
    for operand, operation in itertools.product(
        (-4, -3, -2, -1, 1, 2, 3, 4), range(1, 7)
    ):
        program = [[operand, operation]]
        state = (register, 0)
        expected = outcome(transition, state, program, None)
        actual = outcome(_advance, state, program, None)
        assert actual == expected
        if actual[1] is None:
            assert type(actual[0][0][0]) is int


@pytest.mark.parametrize("shard", range(16))
def test_nested_control(shard):
    programs = [
        [[code] for code in codes]
        for length in (1, 2, 3)
        for codes in itertools.product(range(1, 9), repeat=length)
    ]
    for program in programs[shard::16]:
        for register, index in itertools.product((-1, 0, 1), range(len(program))):
            state = (register, index)
            expected = outcome(transition, state, program, None)
            actual = outcome(_advance, state, program, None)
            assert actual == expected
            if actual[1] is None:
                assert (
                    _advance(state, program, None, _bracket_pairs(program)) == actual[0]
                )


@pytest.mark.parametrize("register", [-2, -1, 0, 1, 65])
@pytest.mark.parametrize("operation", [1, 2])
@pytest.mark.parametrize("byte", [None, 0, 10, 65])
def test_valid_io_transitions(register, operation, byte):
    program = [[0, operation]]
    state = (register, 0)
    assert outcome(_advance, state, program, byte) == outcome(
        transition, state, program, byte
    )


@pytest.mark.parametrize("operator", range(1, 7))
def test_zero_operand_roots(operator):
    source = encode([[0, operator], [1, 1], [0, 1]])
    io = ScriptedIO("A")
    vm = _Machine(source, io)
    expected = parse(source)
    assert tuple(tuple(instruction) for instruction in vm.instructions) == expected
    while not vm.halted:
        vm.step()
    if operator > 2:
        assert io.reads == 0
        assert io.getvalue() == chr(1)


def test_cursorless_progress():
    class Cursorless(ScriptedIO):
        def position(self):
            return 0

    source = encode([[1, 1], [5], [0, 2], [0, 1], [1, 1], [6]])
    io = Cursorless("AAAA")
    vm = _Machine(source, io)
    seen = set()
    for _ in range(100):
        if vm.halted:
            break
        snap = vm.snapshot()
        assert snap not in seen
        seen.add(snap)
        vm.step()
    else:
        raise AssertionError("input loop failed to halt")
    assert io.reads == 4
    assert io.getvalue() == "AAAA"


def test_program_identity():
    a = _Machine(encode([[1, 1]]), ScriptedIO(""))
    b = _Machine(encode([[1, 2]]), ScriptedIO(""))
    assert a.snapshot() != b.snapshot()


@pytest.mark.parametrize("text", ["", "\0", "λ", "\n"])
def test_input_machine_state(text):
    from tests.interpreters.polynomial_reference import Reference

    program = [[0, 2]]
    source = encode(program)
    io = ScriptedIO(text)
    vm = _Machine(source, io)
    ref = Reference(program, text)
    ref.step()
    vm.step()
    assert vm.snapshot() == (ref.cursor, ref.register, ref.offset, ref.reads, ((0, 2),))
    assert (io.position(), io.reads) == (ref.offset, ref.reads)


def test_primality_reference():
    from math import isqrt

    from esolangs.interpreters.register_based.polynomial import prime

    for number in range(2, 10001):
        assert prime(number) == all(
            number % divisor for divisor in range(2, isqrt(number) + 1)
        )
