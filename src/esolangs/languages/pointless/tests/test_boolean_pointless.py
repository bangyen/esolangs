"""Tests for the Pointless Boolean generator."""

import pytest

import esolangs

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
