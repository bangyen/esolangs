"""addsubjump generator tests."""

import random

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import tools as boolean
from esolangs.tools.addsubjump import (
    _addsubjump_ordered,
    _addsubjump_packed,
    addsubjump,
)
from esolangs.tools.helpers import in_input_order
from tests.generator_support import assert_parity_at_most_doubles
from tests.tools.boolean_runners import (
    run_addsubjump,
    run_addsubjump_from,
)
from tests.witness_tables import witnesses


class TestAddSubJump:
    def test_branch_normalizes_ascii_bits(self) -> None:
        """Each ASCII input contributes its zero-or-one value to the index."""
        program = boolean.addsubjump("0110")
        assert "48" in program
        assert run_addsubjump(program, ["0", "1"]) == "1"
        assert run_addsubjump(program, ["1", "0"]) == "1"

    @pytest.mark.medium
    def test_all_three_input_tables(self) -> None:
        """The packed decoder executes the three-input witnesses."""
        for table in witnesses(3):
            program = boolean.addsubjump(table)
            for row in range(8):
                bits = [str((row >> shift) & 1) for shift in (2, 1, 0)]
                assert run_addsubjump(program, bits) == table[row]

    def test_three_input_total(self) -> None:
        """Shared residuals reduce the n=3 total from 105,924 to 96,084."""
        total = sum(len(boolean.addsubjump(f"{value:08b}")) for value in range(256))
        assert total == 96084

    def test_every_path_reads_each_input_once(self) -> None:
        """A run consumes exactly ``n`` inputs, whatever the table."""
        for table, n in (("01101001", 3), ("11111111", 3), ("10101010", 3)):
            program = boolean.addsubjump(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_addsubjump_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.addsubjump, range(11, 15))


# Sharing preserves ordered input consumption and the size admission gate.


def _parent(table: str) -> str:
    return (
        in_input_order(table, _addsubjump_ordered)
        if len(table) <= 16
        else _addsubjump_packed(table)
    )


@pytest.mark.slow
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
                vm = debugger_api.make_vm(
                    "AddSubJump",
                    program,
                    stdin=esolangs.encode_inputs("AddSubJump", bits),
                )
                for _ in range(100_000):
                    if vm.halted:
                        break
                    vm.step()
                assert vm.halted
                assert esolangs.read_answer("AddSubJump", vm.output) == expected
                assert vm.snapshot()[-1] == n
        totals[n] = before, after
    assert totals[3] == (105924, 96084)
    assert totals[5] == (252406, 205998)
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
            stdin=esolangs.encode_inputs("AddSubJump", bits),
            timeout=None,
        )
        assert esolangs.read_answer("AddSubJump", output) == expected


@pytest.mark.medium
@pytest.mark.parametrize(
    "n",
    [
        6,
        8,
        pytest.param(10, marks=pytest.mark.slow),
        pytest.param(12, marks=pytest.mark.slow),
    ],
)
def test_packed_cells_execute(n: int) -> None:
    rng = random.Random(n)
    tables = [
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        f"{rng.getrandbits(1 << n):0{1 << n}b}",
    ]
    for table in tables:
        program = addsubjump(table)
        rows = range(len(table)) if n == 6 else (0, 1, len(table) // 2, len(table) - 1)
        for row in rows:
            bits = [(row >> shift) & 1 for shift in reversed(range(n))]
            output = esolangs.run(
                "AddSubJump",
                program,
                stdin=esolangs.encode_inputs("AddSubJump", bits),
                timeout=None,
            )
            assert esolangs.read_answer("AddSubJump", output) == table[row]
