"""Tests for the What!? Boolean generator."""

import random

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("What!?", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("What!?", bits)
        got = esolangs.run("What!?", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("What!?", got) == table[row], (table, row)


@pytest.mark.medium
def test_a_table_past_the_low_input_cap_labels_its_blocks() -> None:
    """n=16 splits into two labelled blocks; rows on both sides answer."""
    table = format(random.Random(1).getrandbits(1 << 16), "065536b")
    program = esolangs.generate("What!?", table)
    for row in (0, 32767, 32768, 65535):
        stdin = esolangs.encode_inputs("What!?", [int(b) for b in format(row, "016b")])
        got = esolangs.run("What!?", program, stdin=stdin, timeout=10)
        assert esolangs.read_answer("What!?", got) == table[row], row
