"""Covers :mod:`esolangs.tools.sbleq`: the shared tree and the packed decoder."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.sbleq import _Machine
from esolangs.tools.helpers import best_input_order
from esolangs.tools.packed_decoder import _packed_build, packed_decoder
from esolangs.tools.sbleq import _sbleq_hoisted
from tests.generator_support import assert_parity_at_most_doubles
from tests.tools.boolean_runners import run_sbleq
from tests.tools.sample_tables import five_input_sample


def _execute_count(program: str, text: str) -> tuple[str, int, int]:
    io = ScriptedIO(text + "extra")
    machine = _Machine(program, io)
    steps = 0
    while not machine.halted:
        machine.step()
        steps += 1
        assert steps < 2_000_000
    return io.getvalue(), io.position(), steps


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_forced_chunk_banks_compute_every_small_table(n: int) -> None:
    for value in range(1 << (1 << n)):
        table = f"{value:0{1 << n}b}"
        literal = _packed_build(table, keep_constant_layout=True)
        banked = _packed_build(table, keep_constant_layout=True, share_chunks=True)
        for row in range(1 << n):
            text = f"{row:0{n}b}"
            before = _execute_count(literal, text)
            after = _execute_count(banked, text)
            assert before[:2] == after[:2] == (table[row], n)
            assert after[2] == before[2] + 2


@pytest.mark.slow
def test_repeated_chunk_bank_crosses_a_large_reference_boundary() -> None:
    n = 16
    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    literal = _packed_build(table)
    banked = packed_decoder(table)
    assert (len(literal), len(banked)) == (32193, 28141)
    for row in (0, 16):
        text = f"{row:0{n}b}"
        before = _execute_count(literal, text)
        after = _execute_count(banked, text)
        assert before[:2] == after[:2] == (table[row], n)
        assert after[2] == before[2] + 2


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_once_and_falls_off_after_output(n: int, bit: str) -> None:
    table = bit * (1 << n)
    for program in (boolean.sbleq(table), packed_decoder(table)):
        for row in range(1 << n):
            text = f"{row:0{n}b}"
            io = ScriptedIO(text + "extra")
            machine = _Machine(program, io)
            for _ in range(n + 1):
                assert not machine.halted
                machine.step()
            assert machine.halted
            assert io.position() == n
            assert io.getvalue() == bit


@pytest.mark.parametrize("n", [3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_balanced_constants_read_every_input(n: int, bit: str) -> None:
    program = esolangs.generate("S*bleq", bit * (1 << n), balance=True)
    for row in range(1 << n):
        io = ScriptedIO(f"{row:0{n}b}" + "extra")
        machine = _Machine(str(program), io)
        for _ in range(n + 3):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert io.position() == n
        assert io.getvalue() == bit


class TestSbleq:
    """The hoisted tree through its sharing, and the packed decoder past it."""

    def test_only_the_hoisted_route_remains(self) -> None:
        """The former node-read builder is gone, not merely bypassed."""
        import importlib

        module = importlib.import_module("esolangs.tools.sbleq")

        assert not hasattr(module, "_sbleq_node_read")

    def test_hoisted_build_reads_every_input_once_up_front(self) -> None:
        """The read block is 2n instructions and precedes every branch."""
        program = _sbleq_hoisted("00010111", (0, 1, 2))
        cells = [int(tok) for tok in program.split()]
        code_base = cells[6]
        code = cells[code_base:]
        triples = [tuple(code[i : i + 3]) for i in range(0, len(code), 3)]
        reads = [t for t in triples[:3] if t[1] == -2]
        assert len(reads) == 3  # one read per input, all before the tree
        assert [t[0] for t in reads] == sorted({t[0] for t in reads})  # input order

    def test_packed_decoder_executes_wide_rows(self) -> None:
        """Rows on both sides of chunk boundaries decode correctly."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = packed_decoder(table)
        for row in (0, 1, 5, 6, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_sbleq(program, bits) == table[row]

    def test_a_repeated_subtree_is_jumped_to(self) -> None:
        """XOR's second test reaches the leaves already emitted for the first."""
        shared = boolean.sbleq("0110").split()
        plain = _sbleq_hoisted("0110", (0, 1)).split()
        # Two two-instruction leaves out, one jump in, three cells apiece.
        assert len(plain) - len(shared) == 3 * (4 - 1)
        assert shared[-3:-1] == ["0", "0"]
        assert shared.count("-3") == plain.count("-3") - 2 == 2

    @staticmethod
    def _sharing_totals(tables: list[str]) -> tuple[int, int]:
        """(before, shipped) totals, each table checked not to grow."""
        before = after = 0
        for table in tables:
            old = len(
                best_input_order(table, _sbleq_hoisted)
                if len(table) <= 16
                else packed_decoder(table)
            )
            new = len(boolean.sbleq(table))
            assert new <= old, table
            before, after = before + old, after + new
        return before, after

    def test_sharing_three_input_total(self) -> None:
        """All 256 three-input tables: 48,078 to 38,360 characters, 20.2%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._sharing_totals(tables) == (48078, 38360)

    def test_sharing_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 323,720 to 62,709 characters, 80.6%."""
        assert self._sharing_totals(five_input_sample()) == (323720, 62709)

    def test_shared_tree_executes_wide_rows(self) -> None:
        """A seeded seven-input table, every row, through the shared tree."""
        n = 7
        table = format(random.Random(7).getrandbits(2**n), f"0{2**n}b")
        program = boolean.sbleq(table)
        assert len(program) < len(packed_decoder(table))
        for row in range(2**n):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_sbleq(program, bits) == table[row]


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.sbleq, range(11, 15))
