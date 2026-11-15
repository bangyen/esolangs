"""Tests for the BracketOnly Boolean generator."""

import esolangs
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses


def test_every_row_prints_its_answer() -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*SMALL_TABLES, *witnesses(3), *witnesses(4), *witnesses(5)):
        n = len(table).bit_length() - 1
        artifact = esolangs.generate("BracketOnly", table)
        program = esolangs.prepare("BracketOnly", artifact)
        for row, answer in enumerate(table):
            stdin = esolangs.encode_inputs("BracketOnly", row_bits(row, n))
            got = program.run(stdin=stdin)
            assert got.output == answer, (table, row)
            assert got.input_reads == n
