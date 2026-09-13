"""Tests for the Vandevelo boolean generator."""

from itertools import product

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.vandevelo import _Machine
from esolangs.tools.vandevelo import vandevelo
from esolangs.vm import run_until_halt_or_cycle


def _result(program: str, bits: tuple[int, ...]) -> str:
    io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
    return "0" if run_until_halt_or_cycle(_Machine(program, io)) else "1"


def test_xor_executes_every_generated_row() -> None:
    program = vandevelo("0110")
    results = (_result(program, bits) for bits in product(range(2), repeat=2))
    assert "".join(results) == "0110"


def test_constant_still_reads_every_input() -> None:
    program = vandevelo("00000000")
    io = ScriptedIO("0\n1\n0\n")
    assert run_until_halt_or_cycle(_Machine(program, io))
    assert io.position() == 3


def test_one_rows_are_named_minterms() -> None:
    program = vandevelo("0001")
    assert program.splitlines()[-1] == "i0? != Nil? :: i1? != Nil? :: loop?"
