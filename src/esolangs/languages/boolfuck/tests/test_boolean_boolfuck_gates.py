"""Native controls for normalized two-input gates and their ledgers."""

import random

import pytest

from esolangs.languages.boolfuck.generator import (
    affine_stream,
    boolfuck,
    normal_gates,
    popcount_stream,
)
from esolangs.languages.boolfuck.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState


def _execute(table: str, program: str, rows: range | list[int]) -> int:
    n = len(table).bit_length() - 1
    # The ledger's execution clause: the tree's bound, or the count
    # build's exact worst where a symmetric table streams its count.
    command_bound = max(2 * n * n + 27 * n + 8, 4 * n * n + 30 * n + 15)
    workspace = (
        (len(program) - 1).bit_length()
        + max(12, (2 * n - 2).bit_length() + 10)
        + n
        + sum(i.bit_length() for i in range(1, n))
        + (2 * n).bit_length()
        + n.bit_length()
    )
    maximum = 0
    for row in rows:
        io = ScriptedIO(f"{row:0{n}b}")
        machine = _Machine(program, io)
        written = WrittenState(machine.snapshot())
        commands = 0
        while not machine.halted and commands <= command_bound:
            machine.step()
            written.sample(machine.snapshot())
            commands += 1
        assert machine.halted
        assert io.getvalue() == table[row]
        assert commands <= command_bound
        assert written.bits <= workspace
        maximum = max(maximum, commands)
    return maximum


def test_small_tables_keep_existing_paths() -> None:
    assert normal_gates("0110") is None
    assert affine_stream("01") is None
    assert affine_stream("0001") is None


@pytest.mark.medium
@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_all_small_affine_functions_consume_ignored_and_selected_bytes(n: int) -> None:
    for mask in range(1 << n):
        for bias in (0, 1):
            table = "".join(
                str(((row & mask).bit_count() & 1) ^ bias) for row in range(1 << n)
            )
            program = affine_stream(table)
            assert program is not None
            assert len(boolfuck(table)) <= len(program)
            _execute(table, program, range(1 << n))


@pytest.mark.parametrize("bias", [0, 1])
def test_cap_affine_stream_uses_constant_space(bias: int) -> None:
    n = 16
    table = "".join(str((row.bit_count() & 1) ^ bias) for row in range(1 << n))
    program = affine_stream(table)
    assert program is not None
    assert len(program) == 271 + 3 * bias
    _execute(table, program, [0, 1, 32767, 32768, 65534, 65535])


@pytest.mark.parametrize("n", [2])
def test_public_and_still_attains_the_tree_execution_bound(n: int) -> None:
    # Where the tree still wins AND, its all-ones row attains the bound
    # the ledger's first term states.
    table = "0" * ((1 << n) - 1) + "1"
    assert _execute(table, boolfuck(table), [(1 << n) - 1]) == 2 * n * n + 27 * n + 8


@pytest.mark.parametrize("n", [3, 4, 5, 6, 9, 10, 16])
def test_public_and_executes_the_count_build_at_its_exact_cost(n: int) -> None:
    # Where the count build wins AND, its all-ones row costs the read
    # phase at full popcount plus the one flip at count n.
    table = "0" * ((1 << n) - 1) + "1"
    assert _execute(table, boolfuck(table), [(1 << n) - 1]) == 3 * n * n + 26 * n + 19


@pytest.mark.parametrize("n", [3, 6, 9, 12])
def test_count_build_attains_the_restated_execution_bound(n: int) -> None:
    # The alternating-bits table flips at every count with f[0] set:
    # the count build's worst row, attaining the ledger's second term.
    table = "".join(str((row.bit_count() + 1) & 1) for row in range(1 << n))
    program = popcount_stream(table)
    assert program is not None
    assert _execute(table, program, [(1 << n) - 1]) == 4 * n * n + 30 * n + 15


# One code per _normal class: constants 0 and 15, literal 3, xor 6, and-type 11.
@pytest.mark.parametrize("code", [0, 3, 6, 11, 15])
def test_every_two_input_function_with_ignored_prefix(code: int) -> None:
    table = f"{code:04b}" * 128
    program = normal_gates(table)
    assert program is not None
    _execute(table, program, [*range(4), *range(508, 512)])


@pytest.mark.medium
@pytest.mark.parametrize("seed", [73017, 73018, 73019])
def test_dense_boundary_tables_read_every_row_within_ledgers(seed: int) -> None:
    rng = random.Random(seed)
    table = "".join(str(rng.randrange(2)) for _ in range(512))
    program = normal_gates(table)
    assert program is not None
    assert len(boolfuck(table)) <= len(program)
    _execute(table, program, range(512))


@pytest.mark.parametrize("constant", ["0", "1"])
def test_early_constant_exit_does_not_dispatch_a_second_output(constant: str) -> None:
    table = constant * 256 + "0001011101101001" * 16
    program = normal_gates(table)
    assert program is not None
    _execute(table, program, [0, 3, 252, 255, 256, 259, 508, 511])


@pytest.mark.medium
# n=16 builds sixteen full programs and runs 64 executions (~4.5-6s CPU),
# straddling the 5s medium ceiling; n=9 is 0.1s.  Only the heavy param sits
# in the slow band, which CI's sharded slow job still runs.
@pytest.mark.parametrize("n", [9, pytest.param(16, marks=pytest.mark.slow)])
def test_extreme_prefix_attains_the_derived_command_bound(n: int) -> None:
    rng = random.Random(9173)
    base = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    maxima = []
    for code in range(16):
        table = base[:-4] + f"{code:04b}"
        program = normal_gates(table)
        assert program is not None
        maxima.append(_execute(table, program, list(range((1 << n) - 4, 1 << n))))
    assert max(maxima) == 2 * n * n + 25 * n + 26


@pytest.mark.medium
def test_boolfuck_scaling_windows_follow_normalized_gate_route() -> None:
    from esolangs.languages.boolfuck.generator import boolfuck, normal_gates
    from tests.proofs.deep.linearity import (
        ARITY_OVERRIDE,
        MAX_DIFF_RATIO,
        _classes,
        _series,
        _trend,
    )
    from tests.support.witness_tables import nested_dense

    series = _series(boolfuck, nested_dense, ARITY_OVERRIDE["boolfuck"])
    windows = _classes(series)
    assert len(windows) == 2
    for window in windows:
        for n, size in window:
            gates = normal_gates(nested_dense(n))
            assert gates is not None
            assert len(gates) == size
            assert boolfuck(nested_dense(n)) == gates
    trend = _trend(series)
    assert trend is not None
    assert trend <= MAX_DIFF_RATIO


# Gate programs whose true cost is a few commands past 2n^2 + 27n + 8: the
# planner must refuse them, so the public program stays within the bound.
@pytest.mark.parametrize(
    "table",
    [
        "1110011111100110000011100110011001110110011110010000111000000000",
        "0101101001010011011000111101010100010011001110110110010100101000"
        "1110111100000111100001010010011111110101110010011001110000011000",
        "1110110010101111000111100010101111011011111101011111001010101101"
        "1100010011101000101110001000101010001111110100010110100000111100",
    ],
)
def test_public_program_stays_within_the_command_bound_past_gate_costs(
    table: str,
) -> None:
    _execute(table, boolfuck(table), range(len(table)))


def test_six_input_table_keeps_its_shared_gate_size() -> None:
    import esolangs

    table = "0001111111110001101100011011110111110000110100010001111110110001"
    assert len(esolangs.generate("Boolfuck", table)) == 633


def test_four_input_table_keeps_its_gate_size() -> None:
    import esolangs

    # The gates race starts at n = 4, where the workspace first holds;
    # this table's winner is the gates program, not the shared tree.
    from esolangs.runtime._evaluate import _evaluate

    table = "0001110100101101"
    program = boolfuck(table)
    assert len(esolangs.generate("Boolfuck", table)) == 191
    assert _evaluate("Boolfuck", program, inputs=4) == table


def test_six_input_table_on_the_command_bound_keeps_its_shared_size() -> None:
    import esolangs

    # The shared-blocks tree's command count equals the bound exactly;
    # admission is inclusive, so the shared program stands.
    table = "1101010010101110011101011010111000000100111101000101111100000101"
    assert len(esolangs.generate("Boolfuck", table)) == 599
    _execute(table, boolfuck(table), range(len(table)))
