"""Covers :mod:`esolangs.tools.sbleq`: the shared tree and the packed decoder."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.sbleq import _Machine
from esolangs.tools.packed_decoder import packed_decoder
from esolangs.tools.sbleq import _sbleq_hoisted
from tests.support.generator_support import assert_parity_at_most_doubles
from tests.tools.boolean_runners import run_sbleq


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
