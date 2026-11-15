"""Help. Boolean generators evaluated on their complete input domains."""

import esolangs
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses


def test_every_row_prints_its_answer() -> None:
    for table in (*SMALL_TABLES, *witnesses(3), *witnesses(4), *witnesses(5)):
        n = len(table).bit_length() - 1
        program = esolangs.prepare("Help.", esolangs.generate("Help.", table))
        for row, expected in enumerate(table):
            stdin = esolangs.encode_inputs("Help.", row_bits(row, n))
            result = program.run(stdin=stdin + "1")
            assert (result.output, result.input_reads, result.input_position) == (
                expected,
                n,
                n,
            ), (table, row)
