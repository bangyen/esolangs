"""Execute Unary's admitted sources and its uncapped tree construction."""

import itertools

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.languages.brainfuck.interpreter import _Machine as BFMachine
from esolangs.languages.unary.generator import _decoded, unary
from esolangs.languages.unary.interpreter import _Machine, decode


def _answer(machine: BFMachine | _Machine) -> tuple[str, int]:
    seen = set()
    for _ in range(10_000):
        if machine.halted:
            return "0", machine.input_position()
        state = machine.snapshot()
        if state in seen:
            return "1", machine.input_position()
        seen.add(state)
        machine.step()
    raise AssertionError("neither halt nor fixed cycle")


@pytest.mark.parametrize(
    "table", ["00", "01", "10", "11", pytest.param("0001", marks=pytest.mark.medium)]
)
def test_generated_sources_execute_every_row(table: str) -> None:
    source = unary(table)
    assert decode(source) == _decoded(table)
    n = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = tuple((row >> shift) & 1 for shift in range(n - 1, -1, -1))
        machine = _Machine(source, ScriptedIO(esolangs.encode_inputs("Unary", bits)))
        assert _answer(machine) == (expected, n)
    if table == "0001":
        assert len(source) == 27_452_351


def test_decoded_construction_exhaustive_through_three_inputs() -> None:
    for n in range(1, 4):
        for entries in itertools.product("01", repeat=1 << n):
            table = "".join(entries)
            code = _decoded(table)
            for row, expected in enumerate(table):
                stdin = "".join(
                    "\xff" if (row >> shift) & 1 else "\x00"
                    for shift in range(n - 1, -1, -1)
                )
                assert _answer(BFMachine(code, ScriptedIO(stdin))) == (expected, n)


@pytest.mark.parametrize("table", ["0110", "0" * 1023 + "1", "0" * 1024])
def test_source_cap_refuses_before_materialization(table: str) -> None:
    with pytest.raises(esolangs.GeneratorCapError, match=r"cap|max-inputs"):
        unary(table)
    assert unary("01")  # Positive control: the cap does not refuse every build.


@pytest.mark.medium
def test_compressed_budget_admits_nine_reads_but_blocks_raw_export() -> None:
    source = unary("0" * 512)
    assert len(source) == 230_087_533
    assert len(source.to_gzip()) == 223_664
    assert decode(source) == "," * 9
    for bit in ("\x00", "\xff"):
        assert _answer(_Machine(source, ScriptedIO(bit * 9))) == ("0", 9)
    with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
        str(source)
