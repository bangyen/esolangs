"""Tests for the Pointless Boolean generator."""

import pytest

import esolangs
from tests.support.event_io import ReadFirstIO

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Pointless", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Pointless", bits)
        got = esolangs.run("Pointless", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Pointless", got) == table[row], (table, row)


def test_a_function_called_once_is_pasted_in() -> None:
    import random
    import re

    from esolangs.languages.pointless.generator import pointless
    from esolangs.runtime._evaluate import _evaluate

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
                program = esolangs.generate("Pointless", bit * (1 << n), **options)
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
    assert (
        sum(len(esolangs.generate("Pointless", format(v, "08b"))) for v in range(256))
        == 121551
    )
