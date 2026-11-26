"""Nybbleist byte framing, bracket history and selector lanes."""

import esolangs
from esolangs.languages.nybbleist.interpreter import run
from esolangs.languages.nybbleist.tests.oracle_checks import check_raw_nybbleist
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses


def test_nybbleist_execution() -> None:
    for source, stdin, expected in (
        ("*7#1#1>X!3X@ [|%0 >X +X1 *X !3X #2 :0 *3 :2]1", "", "47"),
        ("[!41]1#1@", "", "AA"),
        ("!414", "", "A@"),
        ("*E2<X>Y$&YF-XF!XY!4@", "", "1@"),
        ("?X?Y*X~X1~X1~X1~X1<X-X1*X:1>X-Y1!XY@", "@", "O"),
    ):
        io = ScriptedIO(stdin)
        run(source, io)
        assert io.getvalue() == expected

    for table in (*SMALL_TABLES, *witnesses(3), *witnesses(4), *witnesses(5)):
        n = len(table).bit_length() - 1
        program = esolangs.prepare("Nybbleist", esolangs.generate("Nybbleist", table))
        for row, answer in enumerate(table):
            stdin = esolangs.encode_inputs("Nybbleist", row_bits(row, n))
            result = program.run(stdin=stdin + "Q").unwrap()
            assert (result.output, result.input_reads, result.input_position) == (
                answer,
                n,
                n,
            ), (table, row)


def test_nybbleist_model() -> None:
    check_raw_nybbleist()
