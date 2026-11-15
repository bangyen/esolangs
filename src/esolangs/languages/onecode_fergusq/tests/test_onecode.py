"""Standalone expressions, jumps and generated lookups."""

import esolangs
from esolangs.languages.onecode_fergusq.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses

_NAME = "Onecode (Fergusq)"


def test_onecode_execution() -> None:
    io = ScriptedIO("-9 c")
    run(
        """
        v~w~getn(); *0~[v, w+3, getc()]; // numeric input leaves its delimiter
        putn(*0/2); putn(*1); putc(*2); putc(getc());
        *0~"🦉"; putc(*0); putn(*1);
        if (1^1) goto wrong; else goto right;
        wrong: putn(7); goto end;
        right: putn((2+3*4)=14); putn((!0&0)|1); putn(0^1);
        end:
        """,
        io,
    )
    assert io.getvalue() == "-4-6 c🦉0111"

    for table in (*SMALL_TABLES, *witnesses(3), *witnesses(4), *witnesses(5)):
        n = len(table).bit_length() - 1
        program = esolangs.prepare(_NAME, esolangs.generate(_NAME, table))
        for row, answer in enumerate(table):
            stdin = esolangs.encode_inputs(_NAME, row_bits(row, n))
            result = program.run(stdin=stdin + "x")
            assert (result.output, result.input_reads, result.input_position) == (
                answer,
                n,
                n,
            ), (table, row)
