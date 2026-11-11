"""S*bleq shared-tree and packed-decoder tests."""

import random
from unittest.mock import patch

import pytest

import esolangs
from esolangs.generation.branch_decoder import hoisted_tree
from esolangs.generation.packed_decoder import packed_decoder
from esolangs.languages.s_bleq import generator as boolean
from esolangs.languages.s_bleq.generator import _compact_tree, _tree_min_chars
from esolangs.languages.s_bleq.interpreter import _Machine
from esolangs.languages.s_bleq.tests.formulas import below_eleven, tree_chars
from esolangs.runtime.io import ScriptedIO
from tests.generators.boolean_runners import _runner
from tests.proofs._witnesses import _sbleq_worst
from tests.proofs.execution import tables as _tables
from tests.support import event_io
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import assert_parity_at_most_doubles

run_sbleq = _runner("s_bleq")


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_once_and_falls_off_after_output(n: int, bit: str) -> None:
    if n == 1 and bit == "0":
        event_io.assert_oisc_constants(
            "S*bleq",
            lambda n, _: (3 * n + 3).bit_length() + n.bit_length(),
            relaxed=True,
        )
    table = bit * (1 << n)
    for program in (boolean.s_bleq(table), packed_decoder(table)):
        for row in range(1 << n):
            event_io.assert_falloff(_Machine, program, n, bit, row, n + 1)


@pytest.mark.parametrize("n", [3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_balanced_constants_read_every_input(n: int, bit: str) -> None:
    program = esolangs.generate("S*bleq", bit * (1 << n), balance=True).source
    for row in range(1 << n):
        event_io.assert_falloff(_Machine, str(program), n, bit, row, n + 3, early=True)


class TestSbleq:
    def test_packed_decoder_executes_wide_rows(self) -> None:
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = packed_decoder(table)
        for row in (0, 1, 5, 6, 7, 31, 32, 62, 63):
            assert run_sbleq(program, list(f"{row:0{n}b}")) == table[row]

    def test_a_repeated_subtree_is_jumped_to(self) -> None:
        """XOR's second test reaches the leaves already emitted for the first."""
        shared = boolean.s_bleq("0110").split()
        # Four leaves, two distinct: each output is emitted once, then jumped to.
        assert shared[-3:-1] == ["0", "0"]
        assert shared.count("-3") == 2

    def test_shared_tree_executes_wide_rows(self) -> None:
        _check_compacted_trees()
        n = 7
        table = format(random.Random(7).getrandbits(2**n), f"0{2**n}b")
        program = boolean.s_bleq(table)
        assert len(program) < len(packed_decoder(table))
        for row in range(2**n):
            assert run_sbleq(program, list(f"{row:0{n}b}")) == table[row]


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.s_bleq, range(11, 15))


@pytest.mark.parametrize("n", [5, 6, 7, 8])
def test_tree_min_chars_never_passes_the_tree_it_prices(n: int) -> None:
    """The race skip's bound is a floor on the tree, on every table tried."""
    seeded = format(random.Random(n).getrandbits(1 << n), f"0{1 << n}b")
    for table in (*_tables("S*bleq", n), seeded, _sbleq_worst(n)):
        for flip in (False, True):
            tree = _compact_tree(hoisted_tree(table, tuple(range(n)), flip=flip), n)
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
    assert boolean.s_bleq(table) == _compact_tree(
        hoisted_tree(table, tuple(range(n))), n
    )
    from tests.generators.generator_sections import named_table

    for query, rule in (
        ("_sbleq_hoisted", "parity"),
        ("packed_decoder", "random 1847"),
    ):
        assert_analysis_complement(
            "S*bleq", query, named_table(10, rule), rows=(0, 1, 1023)
        )
    table = named_table(10, "parity")
    original = boolean.s_bleq(table)
    packed = packed_decoder(table)
    with patch.object(
        boolean, "_tree_min_chars", return_value=len(packed) + 1
    ) as false_floor:
        assert boolean.s_bleq(table) == packed
        assert false_floor.called
    assert len(packed) > len(original)
    for row in (0, 1, 1023):
        bits = list(f"{row:010b}")
        assert run_sbleq(original, bits) == run_sbleq(packed, bits) == table[row]


@pytest.mark.parametrize("n", [3, 4, 5, 8, 10])
def test_size_below_eleven_inputs_is_at_most_the_shorter_route(n: int) -> None:
    """The ledger's ``worst P`` starts at n = 11; below, min(tree, P) bounds it."""
    bound = below_eleven(n) if n >= 5 else tree_chars(n)
    for table in _tables("S*bleq", n):
        assert len(esolangs.generate("S*bleq", table).source) <= bound, table


def test_flipped_tree_ends_the_and_relay_jumps() -> None:
    """AND's repeated zero half is a jump target when the test branches on 0."""
    n = 8
    table = "0" * (2**n - 1) + "1"
    nor = "1" + "0" * (2**n - 1)
    assert len(boolean.s_bleq(table)) < 0.9 * len(hoisted_tree(table, tuple(range(n))))
    assert len(boolean.s_bleq(table)) < 1.2 * len(boolean.s_bleq(nor))


def _check_compacted_trees() -> None:
    """Relocated targets stay disjoint from destructive inputs and code."""
    for table in ("0110", "00001100", "01101001", "1101001101101101"):
        n = len(table).bit_length() - 1

        for flip in (False, True):
            old = hoisted_tree(table, tuple(range(n)), flip=flip)
            program = _compact_tree(old, n)
            initial = list(map(int, program.split()))
            literal = initial.index(-49)
            assert len(program) < len(old)
            for row in range(1 << n):
                io = event_io.ReadFirstIO(f"{row:0{n}b}!", expected=n)
                machine = _Machine(program, io)
                steps = 0
                while not machine.halted:
                    machine.step()
                    assert machine.mem[literal] == -49
                    steps += 1
                    assert steps <= 3 * n + 2
                assert io.getvalue() == table[row]
                assert io.past_end == 0
                assert io.input_char() == ord("!")


def test_packed_execution_bound_recognizes_the_emitted_cells() -> None:
    from esolangs.languages.s_bleq.proof_formulas import _packed_steps
    from scripts.docs.resource_evidence import resource_bounds

    execution = resource_bounds("S*bleq")["execution"].formula
    for n in (5, 6, 10):
        table = format(random.Random(1847).getrandbits(1 << n), f"0{1 << n}b")
        program = packed_decoder(table)
        bound = _packed_steps(n, list(map(int, program.split())))
        assert bound is not None
        assert execution(n, program) == bound
        peak = 0
        rows = range(1 << n) if n <= 6 else (0, 1, 511, 512, 1023)
        for row in rows:
            io = ScriptedIO(f"{row:0{n}b}" + "Q")
            machine = _Machine(program, io)
            steps = event_io.count_steps(machine, bound)
            assert io.getvalue() == table[row]
            assert io.reads == n
            assert io.input_char() == ord("Q")
            peak = max(peak, steps)
        if n <= 6:
            assert peak == bound
