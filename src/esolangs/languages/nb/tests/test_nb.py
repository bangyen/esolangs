"""NB's overloaded delimiter, arithmetic and generated branches."""

import esolangs
from esolangs.languages.nb.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses


def test_nb_execution() -> None:
    io = ScriptedIO("2 -3")
    run(
        "bnb nn nbb nn bnb nnn nnn bbbbbb nbnb bnb"
        " nn bbbbb nb nbn nn nbn nnn bb nn nn bbbbb nb bn",
        io,
    )
    assert io.getvalue() == "1-6"
    assert io.reads == 2

    io = ScriptedIO("0")
    run("BNB NN NBB NN NBN NB BNN NBN NBNB BBB", io)
    assert io.getvalue() == "2"

    for table in (*SMALL_TABLES, *witnesses(3), *witnesses(4), *witnesses(5)):
        n = len(table).bit_length() - 1
        program = esolangs.prepare("NB", esolangs.generate("NB", table))
        for row, answer in enumerate(table):
            stdin = esolangs.encode_inputs("NB", row_bits(row, n))
            result = program.run(stdin=stdin.rstrip() + "\nx")
            assert (result.output, result.input_reads, result.input_position) == (
                answer,
                n,
                len(stdin.rstrip()),
            ), (table, row)
