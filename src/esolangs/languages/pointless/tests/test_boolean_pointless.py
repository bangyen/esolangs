"""Tests for the Pointless Boolean generator."""

import random
import re

import esolangs
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer(monkeypatch) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        assert_every_row("Pointless", table)

    from esolangs.generation.helpers import subtree_ids
    from esolangs.languages.pointless import generator

    assert generator.subtree_ids is subtree_ids
    monkeypatch.setattr(
        generator,
        "subtree_ids",
        lambda table: [[1] * len(layer) for layer in subtree_ids(table)],
    )
    assert _evaluate("Pointless", generator.pointless("0001"), inputs=2) == "1111"


def test_a_function_called_once_is_pasted_in() -> None:
    from esolangs.languages.pointless.generator import pointless

    table = format(random.Random(1847).getrandbits(64), "064b")
    program = pointless(table)
    names = re.findall(r'"([^"]*)"(\{?)', program)
    declared = [name for name, brace in names if brace]
    calls = [name for name, brace in names if not brace]
    assert declared
    assert all(calls.count(name) > 1 for name in declared)
    assert _evaluate("Pointless", program, inputs=6) == table
    # A positive control: printing the other digit changes the answers.
    mutant = program.replace("<.>", "<<.>>", 1)
    assert _evaluate("Pointless", mutant, inputs=6) != table


def test_constant_audit_read_first_and_sentinel() -> None:
    from esolangs.languages.pointless.interpreter import _Machine

    for n in range(1, 13):
        rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate(
                    "Pointless", bit * (1 << n), **options
                ).source
                if not options:
                    assert len(program) == n + 148 + int(bit)
                for row in rows:
                    io = ReadFirstIO(
                        esolangs.encode_inputs(
                            "Pointless", list(map(int, format(row, f"0{n}b")))
                        )
                        + "Q",
                        expected=n,
                    )
                    machine = _Machine(program, io)
                    steps = 0
                    while not machine.halted and steps <= n + 149:
                        machine.step()
                        steps += 1
                    assert machine.halted
                    assert io.getvalue() == bit
                    assert io.reads == n
                    assert io.input_char() == ord("Q")


def test_constant_audit_three_input_corpus_size() -> None:
    assert three_input_corpus_size("Pointless") == 121551
