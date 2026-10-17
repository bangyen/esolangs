"""Native NOR circuits, repeated cofactors, and the unchanged Suffolk ledgers."""

import random

import pytest

from esolangs.languages.suffolk.generator import (
    _nor,
    _suffolk_lookup,
    shared_dag,
    suffolk,
)
from esolangs.languages.suffolk.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState


@pytest.mark.parametrize("target", [0, 1, 48])
@pytest.mark.parametrize(("left", "right"), [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_nor_cancels_the_targets_old_value(target, left, right) -> None:
    code = _nor(2, 0, 1)
    machine = _Machine(code, ScriptedIO(""))
    machine.state = (0, 0, 0, (left, right, target))
    for _ in code:
        machine.step()
    assert machine.tape[2] == int(not (left or right))


def _execute(table, program, rows):
    n = len(table).bit_length() - 1
    bases = (len(program) - 1).bit_length() + max(6, n - 1) + max(19, 4 * n - 1)
    cap = bases + n.bit_length() + 4
    peak = 0
    for row in rows:
        machine = _Machine(program, ScriptedIO(f"{row:0{n}b}"))
        written = WrittenState(machine.snapshot())
        steps = 0
        while not machine.halted and steps <= len(program) + 151:
            machine.step()
            written.sample(machine.snapshot())
            steps += 1
        assert machine.halted
        assert machine.io.getvalue() == table[row]
        assert machine.io.progress() == n
        assert written.bits <= cap
        peak = max(peak, steps)
    assert peak <= len(program) + 151


def _witness_rows(n):
    """Rows 0, all-ones, single-bit and low-run rows plus complements, 32 seeded."""
    top = (1 << n) - 1
    rows = {0, top}
    for k in range(n):
        rows |= {1 << k, top ^ (1 << k), (1 << k) - 1, top ^ ((1 << k) - 1)}
    return sorted(rows | set(random.Random(n).sample(range(1 << n), 32)))


@pytest.mark.medium
@pytest.mark.parametrize("n", [9, 10])
def test_changed_scaling_controls_execute_witness_rows(n) -> None:
    table = "".join(str((i * 73 + i.bit_count()) & 1) for i in range(1 << n))
    old, new = _suffolk_lookup(table), suffolk(table)
    assert len(new) < len(old)
    _execute(table, old, _witness_rows(n))
    _execute(table, new, _witness_rows(n))


@pytest.mark.medium
@pytest.mark.parametrize("start", range(0, 256, 32))
def test_shared_parity_executes_both_ignored_input_fills(start) -> None:
    core = "".join(str(row.bit_count() & 1) for row in range(256))
    table = core * 256
    program = shared_dag(table, 16)
    assert program is not None
    assert len(program) == 2461
    assert suffolk(table) == program
    rows = [fill << 8 | row for fill in (0, 255) for row in range(start, start + 32)]
    _execute(table, program, rows)


def test_workspace_refusal_preserves_lookup() -> None:
    table = "".join(str(row.bit_count() & 1) for row in range(256))
    assert shared_dag(table, 8) is None
    assert suffolk(table) == _suffolk_lookup(table)


@pytest.mark.parametrize("table", ["00", "11"])
def test_constants_keep_the_stream_drain(table) -> None:
    assert shared_dag(table, 1) is None
    assert suffolk(table) == _suffolk_lookup(table)


def test_repeated_passes_overwrite_every_shared_value() -> None:
    table = "01101001" * 4
    program = shared_dag(table, 5)
    assert program is not None
    machine = _Machine(program, ScriptedIO("00000" + "11111" + "01001"))
    while not machine.halted:
        machine.step()
    assert machine.io.getvalue() == table[0] + table[31] + table[9]


def test_dag_at_the_pointer_bit_boundary_stays_shared() -> None:
    """10 essential inputs and 17 muxes sit exactly on the tape cap."""
    table = "".join(
        str(int((row >> 2).bit_count() % 2 == 1 and row & 3 == 3))
        for row in range(1 << 10)
    )
    program = suffolk(table)
    assert len(program) == 3060
    _execute(table, program, _witness_rows(10)[:8])
