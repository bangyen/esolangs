"""Standalone expressions, jumps and generated lookups."""

import subprocess
import sys
from pathlib import Path

import esolangs
from esolangs.languages.onecode_fergusq.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses

_NAME = "Onecode (Fergusq)"


def test_onecode_execution(tmp_path: Path) -> None:
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
    _check_nested_expressions()

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

    api = esolangs.Language(_NAME)
    dbg = api.make_debugger("*(-2)~19; *2~13; putn(*(-2));")
    dbg.break_on_cell(4, 13)
    assert dbg.run(limits=esolangs.ExecutionLimits(max_steps=30)) == "breakpoint"
    assert dbg.memory == [19, 0, 0, 0, 13]
    assert dict(dbg.views)["origin"] == "2"

    source = tmp_path / "identity.onecode"
    api.to_file(api.generate("01"), source)
    entry = Path(__file__).resolve().parents[1] / "interpreter.py"
    child = subprocess.run(
        [sys.executable, str(entry), str(source)],
        input=api.encode_inputs([1]),
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout == "Input: 1"


def _check_nested_expressions() -> None:
    api = esolangs.Language(_NAME)
    depth = 600
    start = "x~" * depth + "(" * depth + "-" * depth + "7"
    source = start + ")" * depth + "; putn(x);"
    steps = 2 * depth + 5
    caps = esolangs.ExecutionLimits(max_steps=steps)
    prepared = api.prepare(source)
    native = api.run(source)
    assert native.output == "7"
    assert prepared.run() == native

    bounded = api.run(source, limits=caps)
    assert bounded.output == native.output
    assert bounded.steps == steps
    assert prepared.run(limits=caps) == bounded
    assert api.run(source, limits=caps, isolated=True) == bounded
    debug = prepared.make_debugger()
    assert debug.run(limits=caps) == "halted"
    assert debug.observation == bounded

    shorter = esolangs.ExecutionLimits(max_steps=steps - 1)
    stopped = api.execute(source, limits=shorter)
    assert isinstance(stopped.error, esolangs.ExecutionCapError)
    assert stopped.observation.output == "7"
    assert stopped.observation.steps == steps - 1

    malformed = api.execute(start + ")" * (depth - 1) + ";")
    assert isinstance(malformed.error, esolangs.ProgramError)
    assert "expected ')', got ';'" in str(malformed.error)
