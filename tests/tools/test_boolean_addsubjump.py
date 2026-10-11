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
from tests.support.generator_support import assert_parity_at_most_doubles
from tests.support.witness_tables import row_bits, witnesses
from tests.tools.boolean_runners import (
    run_addsubjump,
    run_addsubjump_from,
)


@pytest.mark.medium
def test_packed_projection_executes_every_three_input_table():
    from esolangs._evaluate import _evaluate
    from esolangs.tools.addsubjump import _addsubjump_packed

    for value in range(256):
        table = f"{value:08b}"
        program = _addsubjump_packed(table)
        legacy = _addsubjump_packed(table, keep_ignored_inputs=True)
        assert len(program) <= len(legacy)
        assert _evaluate("AddSubJump", program, inputs=3) == table


@pytest.mark.medium
@pytest.mark.parametrize("kind", ["zero", "one", "first", "last", "ends"])
def test_wide_packed_projection_keeps_reads_and_old_balanced_score(kind):
    from esolangs._evaluate import _evaluate
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.addsubjump import _Machine
    from esolangs.tools.addsubjump import _addsubjump_packed
    from esolangs.tools.wrap import balance_program, balance_score
    from esolangs.vm import run_until_halt_or_cycle

    table = (
        str(int(kind == "one")) * 256
        if kind in ("zero", "one")
        else "".join(
            str(
                (
                    (row >> 7)
                    if kind == "first"
                    else row & 1
                    if kind == "last"
                    else (row >> 7) + (row & 1)
                )
                % 2
            )
            for row in range(256)
        )
    )
    program = boolean.addsubjump(table)
    legacy = _addsubjump_packed(table, keep_ignored_inputs=True)
    assert len(program) < len(legacy)
    assert _evaluate("AddSubJump", program, inputs=8) == table
    balanced = esolangs.generate("AddSubJump", table, balance=True)
    assert balance_score(balanced) <= balance_score(
        balance_program(legacy, "addsubjump")
    )
    assert _evaluate("AddSubJump", balanced, inputs=8) == table
    for row in (0, 1, 128, 255):
        bits = [int(c) for c in f"{row:08b}"]
        stdin = esolangs.encode_inputs("AddSubJump", bits)
        io = ScriptedIO(stdin + "0")
        run_until_halt_or_cycle(_Machine(program, io))
        assert io.position() == 8
        assert io.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("essential", range(1, 8))
def test_packed_projection_indexes_nonadjacent_coordinates(essential):
    from esolangs._evaluate import _evaluate
    from esolangs.tools.addsubjump import _addsubjump_packed

    used = [*range(essential - 1), 7]
    table = "".join(
        str(sum((row >> (7 - bit)) & 1 for bit in used) % 2) for row in range(256)
    )
    program = boolean.addsubjump(table)
    assert len(program) <= len(_addsubjump_packed(table, keep_ignored_inputs=True))
    assert _evaluate("AddSubJump", program, inputs=8) == table


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
                bits = row_bits(combo, n)
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
