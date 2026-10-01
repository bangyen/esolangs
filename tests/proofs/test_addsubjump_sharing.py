"""Sharing preserves ordered input consumption and the size admission gate."""

import random

import pytest

import esolangs
from esolangs.tools.addsubjump import (
    _addsubjump_ordered,
    _addsubjump_packed,
    addsubjump,
)
from esolangs.tools.helpers import best_input_order


def _parent(table: str) -> str:
    return (
        best_input_order(table, _addsubjump_ordered)
        if len(table) <= 16
        else _addsubjump_packed(table)
    )


@pytest.mark.medium
def test_sharing_admission() -> None:
    rng = random.Random(0)
    five = sorted({f"{rng.getrandbits(32):032b}" for _ in range(200)})
    assert len(five) == 200
    old = new = 0
    totals = {}
    for n, tables in [
        (1, [f"{i:02b}" for i in range(4)]),
        (2, [f"{i:04b}" for i in range(16)]),
        (3, [f"{i:08b}" for i in range(256)]),
        (5, five),
    ]:
        before = after = 0
        for table in tables:
            parent, program = _parent(table), addsubjump(table)
            assert len(program) <= len(parent)
            before += len(parent)
            after += len(program)
            if n == 5:
                old += len(parent)
                new += len(program)
            for row, expected in enumerate(table):
                bits = [(row >> shift) & 1 for shift in reversed(range(n))]
                vm = esolangs.make_vm(
                    "AddSubJump", program, esolangs.encode_inputs("AddSubJump", bits)
                )
                for _ in range(100_000):
                    if vm.halted:
                        break
                    vm.step()
                assert vm.halted
                assert esolangs.read_answer("AddSubJump", vm.output) == expected
                assert vm.snapshot()[-1] == n
        totals[n] = before, after
    assert totals[3] == (99032, 95678)
    assert totals[5] == (252406, 217608)
    assert new <= 0.95 * old


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 4, 6])
def test_sharing_boundaries(n: int) -> None:
    rng = random.Random(n)
    table = f"{rng.getrandbits(1 << n):0{1 << n}b}"
    program = addsubjump(table)
    assert len(program) <= len(_parent(table))
    for row, expected in enumerate(table):
        bits = [(row >> shift) & 1 for shift in reversed(range(n))]
        output = esolangs.run(
            "AddSubJump",
            program,
            esolangs.encode_inputs("AddSubJump", bits),
            timeout=None,
        )
        assert esolangs.read_answer("AddSubJump", output) == expected
