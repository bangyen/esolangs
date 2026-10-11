"""Subleq generator tests."""

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.subleq import _Machine
from esolangs.tools.packed_decoder import packed_decoder
from esolangs.tools.subleq import subleq


def _execute_count(program: str, text: str) -> tuple[str, int, int]:
    io = ScriptedIO(text + "extra")
    machine = _Machine(program, io)
    steps = 0
    while not machine.halted:
        machine.step()
        steps += 1
        assert steps < 2_000_000
    return io.getvalue(), io.position(), steps


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_once_and_falls_off_after_output(n: int, bit: str) -> None:
    table = bit * (1 << n)
    for width in (None, 1, 20):
        program = esolangs.generate("Subleq", table, width=width)
        for row in range(1 << n):
            io = ScriptedIO(f"{row:0{n}b}" + "extra")
            machine = _Machine(str(program), io)
            for _ in range(n + 1):
                assert not machine.halted
                machine.step()
            assert machine.halted
            assert io.position() == n
            assert io.getvalue() == bit


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_public_candidate_computes_every_small_table(n):
    for value in range(1 << (1 << n)):
        table = f"{value:0{1 << n}b}"
        public = subleq(table)
        assert len(public) <= len(packed_decoder(table, direct=True))
        for row, bit in enumerate(table):
            output, reads, steps = _execute_count(public, f"{row:0{n}b}")
            assert (output, reads) == (bit, n)
            assert steps <= 5 * n + 3


@pytest.mark.medium
def test_shared_parity_uses_direct_jumps_at_sixteen_inputs():
    n = 16
    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    program = subleq(table)
    assert len(program) == 890
    for row in (0, 1, 16, 255, 65535):
        output, reads, steps = _execute_count(program, f"{row:0{n}b}")
        assert (output, reads) == (table[row], n)
        assert steps <= 5 * n + 3
