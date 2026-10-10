"""Native controls for normalized two-input gates and their ledgers."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.boolfuck import _Machine
from esolangs.tools.boolfuck import boolfuck
from esolangs.tools.boolfuck_gates import affine_stream, normal_gates
from scripts.benchmark import WrittenState


def _execute(table: str, program: str, rows: range | list[int]) -> int:
    n = len(table).bit_length() - 1
    command_bound = 2 * n * n + 27 * n + 8
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


@pytest.mark.parametrize("n", [2, 3, 4, 6, 9, 10, 16])
def test_public_and_still_attains_the_existing_execution_bound(n: int) -> None:
    table = "0" * ((1 << n) - 1) + "1"
    assert _execute(table, boolfuck(table), [(1 << n) - 1]) == 2 * n * n + 27 * n + 8


@pytest.mark.parametrize("code", range(16))
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
