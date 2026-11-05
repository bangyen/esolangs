"""Subleq generator tests."""

import pytest

import esolangs
from esolangs.generation.packed_decoder import packed_decoder
from esolangs.languages.subleq.generator import subleq
from esolangs.languages.subleq.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.support.event_io import ReadFirstIO


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
    if n == 1 and bit == "0":
        _check_constants()
    table = bit * (1 << n)
    for width in (None, 1, 20):
        program = esolangs.generate("Subleq", table, width=width).source
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
def test_public_candidate_computes_every_small_table(n) -> None:
    if n == 1:
        _check_io_targets()
    for value in range(1 << (1 << n)):
        table = f"{value:0{1 << n}b}"
        public = subleq(table)
        assert len(public) <= len(packed_decoder(table, direct=True))
        for row, bit in enumerate(table):
            output, reads, steps = _execute_count(public, f"{row:0{n}b}")
            assert (output, reads) == (bit, n)
            assert steps <= 5 * n + 3


@pytest.mark.medium
def test_shared_parity_uses_direct_jumps_at_sixteen_inputs() -> None:
    n = 16
    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    program = subleq(table)
    assert len(program) == 863
    for row in (0, 1, 16, 255, 65535):
        output, reads, steps = _execute_count(program, f"{row:0{n}b}")
        assert (output, reads) == (table[row], n)
        assert steps <= 5 * n + 3


def _check_constants() -> None:
    from esolangs.languages.subleq.interpreter import _Machine
    from esolangs.languages.subleq.proof_formulas import workspace
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Subleq", bit * (1 << n), **options).source
                if not options:
                    assert len(program) == 7 * n + 7
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Subleq", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "7", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                        assert steps <= n + 1
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_char() == ord("7")
                    assert steps == n + 1
                    assert written.bits <= workspace(n, program)
                    peak = max(peak, written.bits)
                assert peak == workspace(n, program)


def _check_io_targets() -> None:
    from esolangs.generation.branch_decoder import hoisted_tree

    for table in ("0110", "00110110", "0110" * 8):
        n = len(table).bit_length() - 1
        for program in (
            hoisted_tree(table, tuple(range(n)), direct=True),
            packed_decoder(table, direct=True),
        ):
            cells = list(map(int, program.split()))
            if cells[0] == 0:
                code, end = cells[2], len(cells)
            else:
                code = 0
                end = next(
                    i
                    for i in range(len(cells) - 4)
                    if cells[i : i + 5] == [0, 1, -1, -48, 48]
                )
            sites = [i for i in range(code, end, 3) if -1 in cells[i : i + 2]]
            assert len(sites) == n + (2 if code else 1)
            assert all(cells[i + 2] == 0 for i in sites)
            for row in range(1 << n):
                output, consumed, _ = _execute_count(program, f"{row:0{n}b}")
                assert (output, consumed) == (table[row], n)

    # A constructive packed peak retains n=9 coverage without a 512-row trace.
    from esolangs.languages.subleq.proof_formulas import workspace
    from scripts.benchmark import WrittenState
    from tests.proofs._witnesses import _subleq_worst

    n = 9
    table = _subleq_worst(n)
    program = subleq(table)
    row = ((1 << n) // n - 1) * n + n - 1
    io = ScriptedIO(f"{row:0{n}b}")
    machine = _Machine(program, io)
    written = WrittenState(machine.workspace_snapshot())
    steps = 0
    while not machine.halted:
        machine.step()
        written.sample(machine.workspace_snapshot())
        steps += 1
        assert steps <= 8 * (1 << n) + (7 * n + 5) * ((1 << n) // n - 1) + 23 * n - 8
    assert io.getvalue() == table[row]
    assert io.reads == n
    assert written.bits == workspace(n, program)
