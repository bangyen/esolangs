"""Emitted Polynomial sources checked against an independent machine."""

import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.polynomial import _Machine
from tests.interpreters.polynomial_generated import decode, generate_with_witness
from tests.interpreters.polynomial_reference import Reference


def check(source, factors, table):
    instructions = decode(source, factors)
    n = len(table).bit_length() - 1
    for row, answer in enumerate(table):
        text = format(row, f"0{n}b")
        reference = Reference([list(item) for item in instructions], text)
        port = ScriptedIO(text)
        machine = _Machine(source, port)
        assert tuple(tuple(item) for item in machine.instructions) == instructions
        for _ in range(10000):
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
                break
            snapshot = machine.snapshot()
            digest = hash(snapshot)
            reference.step()
            machine.step()
            assert hash(snapshot) == digest
        else:
            raise AssertionError("generated program did not halt")
        assert reference.output == answer
        assert reference.reads == n


TABLES = [
    format(value, f"0{1 << n}b") for n in range(1, 4) for value in range(1 << (1 << n))
]


@pytest.mark.medium
@pytest.mark.parametrize("table", TABLES)
def test_public_source(table):
    source, factors = generate_with_witness(table)
    check(source, factors, table)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("table", "level"),
    [(table, level) for table in TABLES for level in range(len(table).bit_length())],
)
def test_hybrid_source(table, level):
    module = importlib.import_module("esolangs.tools.polynomial")
    instructions = module.__dict__["_polynomial_hybrid"](table, level)
    check(
        module.__dict__["_polynomial_assemble"](instructions),
        module.__dict__["_polynomial_factors"](instructions),
        table,
    )


@pytest.mark.medium
@pytest.mark.parametrize(
    "table",
    [
        table
        for table in TABLES
        if table[: len(table) // 2] == table[len(table) // 2 :] and len(set(table)) > 1
    ]
    + ["0000010100000101"],
)
def test_drained_source(table):
    module = importlib.import_module("esolangs.tools.polynomial")
    instructions = module.__dict__["_polynomial_drained_dag"](table)
    assert instructions is not None
    check(
        module.__dict__["_polynomial_assemble"](instructions),
        module.__dict__["_polynomial_factors"](instructions),
        table,
    )


@pytest.mark.parametrize("table", ["0000", "1111"])
def test_constant_machine_and_hybrid_cost_execute(table):
    module = importlib.import_module("esolangs.tools.polynomial")
    for instructions in (
        module.__dict__["_polynomial_dag"](table),
        module.__dict__["_polynomial_hybrid"](table, 0),
    ):
        source = module.__dict__["_polynomial_assemble"](instructions)
        factors = module.__dict__["_polynomial_factors"](instructions)
        check(source, factors, table)
    assert module.__dict__["_polynomial_hybrid_cost"](table, 0) == len(
        decode(source, factors)
    )
