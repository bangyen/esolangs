"""Covers :mod:`esolangs.languages.s_bleq.generator`: the shared tree and the
packed decoder."""

import random

import pytest

import esolangs
from esolangs.generation.branch_decoder import hoisted_tree
from esolangs.generation.packed_decoder import packed_decoder
from esolangs.languages import generators as boolean
from esolangs.languages.s_bleq.generator import _tree_min_chars
from esolangs.languages.s_bleq.interpreter import _Machine
from esolangs.languages.s_bleq.tests.formulas import below_eleven, tree_chars
from esolangs.runtime.io import ScriptedIO
from tests.generators.boolean_runners import _runner
from tests.proofs._witnesses import _sbleq_worst
from tests.proofs.test_execution_formulas import _tables
from tests.support.generator_support import assert_parity_at_most_doubles

run_sbleq = _runner("s_bleq")


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_once_and_falls_off_after_output(n: int, bit: str) -> None:
    table = bit * (1 << n)
    for program in (boolean.s_bleq(table), packed_decoder(table)):
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
        shared = boolean.s_bleq("0110").split()
        # Four leaves, two distinct: each output is emitted once, then jumped to.
        assert shared[-3:-1] == ["0", "0"]
        assert shared.count("-3") == 2

    def test_shared_tree_executes_wide_rows(self) -> None:
        """A seeded seven-input table, every row, through the shared tree."""
        n = 7
        table = format(random.Random(7).getrandbits(2**n), f"0{2**n}b")
        program = boolean.s_bleq(table)
        assert len(program) < len(packed_decoder(table))
        for row in range(2**n):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_sbleq(program, bits) == table[row]


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.s_bleq, range(11, 15))


@pytest.mark.parametrize("n", [5, 6, 7, 8])
def test_tree_min_chars_never_passes_the_tree_it_prices(n: int) -> None:
    """The race skip's bound is a floor on the tree, on every table tried."""
    seeded = format(random.Random(n).getrandbits(1 << n), f"0{1 << n}b")
    for table in (*_tables("S*bleq", n), seeded, _sbleq_worst(n)):
        for flip in (False, True):
            tree = hoisted_tree(table, tuple(range(n)), flip=flip)
            assert _tree_min_chars(table, n) <= len(tree), (table, flip)


def test_the_scaling_witness_skips_the_tree() -> None:
    """At n = 12 the bound passes the packed length, so it ships unraced."""
    n = 12
    table = _sbleq_worst(n)
    packed = packed_decoder(table)
    assert _tree_min_chars(table, n) > len(packed)
    assert boolean.s_bleq(table) == packed


def test_parity_still_runs_the_race_and_ships_the_tree() -> None:
    """Parity's bound stays low: the race runs and the tree wins it."""
    n = 12
    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    assert _tree_min_chars(table, n) <= len(packed_decoder(table))
    assert boolean.s_bleq(table) == hoisted_tree(table, tuple(range(n)))


@pytest.mark.parametrize("n", [3, 4, 5, 8, 10])
def test_size_below_eleven_inputs_is_at_most_the_shorter_route(n: int) -> None:
    """The ledger's ``worst P`` starts at n = 11; below, min(tree, P) bounds it."""
    bound = below_eleven(n) if n >= 5 else tree_chars(n)
    for table in _tables("S*bleq", n):
        assert len(esolangs.generate("S*bleq", table)) <= bound, table


def test_flipped_tree_ends_the_and_relay_jumps() -> None:
    """AND's repeated zero half is a jump target when the test branches on 0."""
    n = 8
    table = "0" * (2**n - 1) + "1"
    nor = "1" + "0" * (2**n - 1)
    assert len(boolean.s_bleq(table)) < 0.9 * len(hoisted_tree(table, tuple(range(n))))
    assert len(boolean.s_bleq(table)) < 1.2 * len(boolean.s_bleq(nor))
