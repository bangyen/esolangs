"""Subleq generator tests."""

import pytest

import esolangs
from esolangs.generation.branch_decoder import hoisted_tree
from esolangs.generation.packed_decoder import packed_decoder
from esolangs.languages.subleq.generator import subleq
from esolangs.languages.subleq.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import assert_falloff, assert_oisc_constants, count_steps


def _execute_count(program: str, text: str) -> tuple[str, int, int]:
    io = ScriptedIO(text + "extra")
    machine = _Machine(program, io)
    steps = count_steps(machine, 1_999_999)
    return io.getvalue(), io.position(), steps


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_once_and_falls_off_after_output(n: int, bit: str) -> None:
    if n == 1 and bit == "0":
        from scripts.docs.resource_evidence import resource_bounds

        workspace = resource_bounds("Subleq")["workspace"].formula

        assert_oisc_constants("Subleq", workspace)
    table = bit * (1 << n)
    for width in (None, 1, 20):
        program = esolangs.generate("Subleq", table, width=width).source
        for row in range(1 << n):
            assert_falloff(_Machine, str(program), n, bit, row, n + 1)


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
    from tests.generators.generator_sections import named_table

    for query, rule in (("hoisted_tree", "parity"), ("packed_decoder", "random 1847")):
        assert_analysis_complement(
            "Subleq", query, named_table(10, rule), rows=(0, 1, 1023)
        )
    n = 16
    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    program = subleq(table)
    assert len(program) == 863
    for row in (0, 1, 16, 255, 65535):
        output, reads, steps = _execute_count(program, f"{row:0{n}b}")
        assert (output, reads) == (table[row], n)
        assert steps <= 5 * n + 3


def _check_io_targets() -> None:
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
    from scripts.docs.resource_evidence import resource_bounds
    from tests.proofs._witnesses import _subleq_worst

    workspace = resource_bounds("Subleq")["workspace"].formula

    n = 9
    table = _subleq_worst(n)
    program = subleq(table)
    row = ((1 << n) // n - 1) * n + n - 1
    io = ScriptedIO(f"{row:0{n}b}")
    machine = _Machine(program, io)
    written = WrittenState(machine.workspace_snapshot())
    cap = 8 * (1 << n) + (7 * n + 5) * ((1 << n) // n - 1) + 23 * n - 8
    count_steps(machine, cap, written=written)
    assert io.getvalue() == table[row]
    assert io.reads == n
    assert written.bits == workspace(n, program)
