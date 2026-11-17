"""Help. byte and address semantics and Boolean execution."""

import pytest

import esolangs
from esolangs.languages.help.interpreter import run
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import make_vm, run_until_halt_or_all_branches_cycle
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses


def _check_byte_instructions() -> None:
    io = ScriptedIO("AB\n")
    run(
        "jmp 3\nout 58\n; this line has an address\n"
        "inp mny $2\n"
        "set 1$0 1234\nout $0 $1 $2 $3\n"
        "add ff 42 $0\nout $0\n"
        "mul 6 8 $0\nout $0\n"
        "sub 39 7 $0\nout $0\n"
        "div 93 3 $0\nout $0\n"
        "mod 65 32 $0\nadd $0 30 $0\nout $0\n"
        "boo $0 not 0\nboo $0 and $0 2\nboo $0 or_ 0 $0\n"
        "add $0 30 $0\nout $0",
        io,
    )
    assert io.getvalue() == "4\x12ABA02111"

    # The seeded path draws 1 and loops. The other outcome reaches end.
    source = "rnd 0 1 $0\nif_ $0\njmp 1\nend"
    machine = make_vm("Help.", source, seed=0)
    assert run_until_halt_or_all_branches_cycle(machine, limit=100)
    assert esolangs.run("Help.", "rnd 41 41 $0\nout $0", seed=0).output == "A"

    api = esolangs.Language("help")
    assert api.name == "Help."
    dbg = api.make_debugger("set $3 13\nset $3 0\nend")
    watched = dbg.watch_cell(3)
    dbg.step()
    assert dbg.memory == [0, 0, 0, 0x13]
    dbg.step()
    assert dbg.memory == []
    assert watched == [0x13, None]
    with pytest.raises(esolangs.UnknownLanguageError) as caught:
        esolangs.describe("Hlp.")
    assert caught.value.suggestions == ("Help.",)


def test_help_execution() -> None:
    _check_byte_instructions()
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
