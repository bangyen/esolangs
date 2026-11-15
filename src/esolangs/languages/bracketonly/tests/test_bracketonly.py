"""BracketOnly raw groups, lazy control flow, and Boolean execution."""

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.languages.bracketonly.interpreter import run
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import make_vm, run_until_halt_or_all_branches_cycle
from tests.support.witness_tables import SMALL_TABLES, row_bits, witnesses


def _call(function: int, *arguments: str) -> str:
    return f"({'()()' * function})({''.join(arguments)})"


def _value(n: int) -> str:
    return _call(1, "()()" * n)


def _check_raw_functions_and_io() -> None:
    io = ScriptedIO("🦉")
    run(_call(9, _call(7)), io)
    assert io.getvalue() == "🦉"

    # Function 8 comes from 3 + 5. Subtraction receives the reads in source order.
    code = f"({_value(3)}{_value(5)})({_call(3, _call(6), _call(6))})"
    io = ScriptedIO("54 12")
    run(code, io)
    assert io.getvalue() == "42"

    answers = {
        1: 6,
        2: 8,
        3: -2,
        4: 0,
        5: 2,
        15: 0,
        16: 6,
        17: 6,
        19: 1,
        20: 0,
        21: 0,
        22: 1,
        23: 1,
        24: 0,
    }
    for function, answer in answers.items():
        io = ScriptedIO()
        run(_call(8, _call(function, _value(2), _value(4))), io)
        assert io.getvalue() == str(answer), function

    io = ScriptedIO()
    run(_call(8, _call(10, "()()", "()()")) + _call(8, _call(18, _value(0))), io)
    assert io.getvalue() == "11"


def _check_control_flow_and_rejected_calls() -> None:
    cell = _value(0)
    read = _call(13, cell)
    body = _call(14, cell, _call(3, read, "()()"))
    loop = _call(12, read, body)
    code = _call(14, cell, _value(4)) + _call(8, _call(11, "()()", loop, _call(7)))
    io = ScriptedIO()
    run(code, io)
    assert io.getvalue() == "6"

    choice = _call(10, cell, "()()")
    loop = _call(12, "()()", cell)
    code = _call(11, choice, loop, cell)
    # Seed 0 draws 1 first, so the live VM would loop; choice 0 halts.
    vm = make_vm("BracketOnly", code, seed=0)
    assert run_until_halt_or_all_branches_cycle(vm, limit=1000)

    for invalid in ("(", "(())()(()())", "(())()", ")(", "()", "[]"):
        with pytest.raises(ValueError, match="BracketOnly"):
            run(invalid, ScriptedIO())
    for function, args in ((25, ()), (17, ("()()",)), (4, ("()()", cell))):
        with pytest.raises(HaltError, match="BracketOnly"):
            run(_call(function, *args), ScriptedIO())


def test_bracketonly_execution() -> None:
    _check_raw_functions_and_io()
    _check_control_flow_and_rejected_calls()
    for table in (*SMALL_TABLES, *witnesses(3), *witnesses(4), *witnesses(5)):
        n = len(table).bit_length() - 1
        program = esolangs.prepare(
            "BracketOnly", esolangs.generate("BracketOnly", table)
        )
        for row, answer in enumerate(table):
            stdin = esolangs.encode_inputs("BracketOnly", row_bits(row, n))
            got = program.run(stdin=stdin)
            assert (got.output, got.input_reads) == (answer, n), (table, row)
