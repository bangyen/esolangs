"""addsubjump generator tests."""

import random
from collections.abc import Iterator

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.generation.helpers import in_input_order
from esolangs.languages import generators as boolean
from esolangs.languages.addsubjump.generator import (
    _addsubjump_ordered,
    _addsubjump_packed,
    addsubjump,
)
from tests.generators.boolean_runners import _run_from, _runner
from tests.support.generator_support import assert_parity_at_most_doubles
from tests.support.witness_tables import row_bits, witnesses

run_addsubjump = _runner("addsubjump")


def run_addsubjump_from(program: str, feed: Iterator[str]) -> str:
    """Run an AddSubJump program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.languages.addsubjump.interpreter", program, feed)


@pytest.mark.medium
def test_packed_projection_executes_every_three_input_table() -> None:
    from esolangs.languages.addsubjump.generator import _addsubjump_packed
    from esolangs.runtime._evaluate import _evaluate

    for value in range(256):
        table = f"{value:08b}"
        program = _addsubjump_packed(table)
        legacy = _addsubjump_packed(table, keep_ignored_inputs=True)
        assert len(program) <= len(legacy)
        assert _evaluate("AddSubJump", program, inputs=3) == table


@pytest.mark.medium
@pytest.mark.parametrize("kind", ["zero", "one", "first", "last", "ends"])
def test_wide_packed_projection_keeps_reads_and_old_balanced_score(kind) -> None:
    from esolangs.generation.wrap import balance_program, balance_score
    from esolangs.languages.addsubjump.generator import _addsubjump_packed
    from esolangs.languages.addsubjump.interpreter import _Machine
    from esolangs.runtime._evaluate import _evaluate
    from esolangs.runtime.io import ScriptedIO
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
def test_packed_projection_indexes_nonadjacent_coordinates(essential) -> None:
    from esolangs.languages.addsubjump.generator import _addsubjump_packed
    from esolangs.runtime._evaluate import _evaluate

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


def test_balancing_retains_legacy_packed_layout_with_an_ignored_input() -> None:
    """Retention is not only for constants: at n=7 an ignored input keeps it.

    Six-input parity padded with an ignored leading input; the full packed
    layout balances strictly better here, as for every such n=7 table.
    """
    from esolangs.generation.wrap import balance_program, balance_score
    from esolangs.languages.addsubjump.generator import _addsubjump_packed
    from tests.support.witness_tables import parity

    table = parity(6) * 2
    legacy = _addsubjump_packed(table, keep_ignored_inputs=True)
    balanced = esolangs.generate("AddSubJump", table, balance=True)
    old = balance_program(legacy, "addsubjump")
    assert balance_score(balanced) <= balance_score(old)


def test_six_input_table_with_five_essential_rows_pins_both_sizes() -> None:
    """Five essential inputs at n=6 take the tree route, and balancing keeps
    the full packed layout when it scores better; both sizes are pinned."""
    table = "0010100100101001011011100110111010011011100110110110101101101011"
    assert len(esolangs.generate("AddSubJump", table)) == 1063
    assert len(esolangs.generate("AddSubJump", table, balance=True)) == 1427


def test_packed_program_prints_then_halts_on_the_special_address() -> None:
    """The packed builder's last instruction prints, then jumps to -8.

    Any negative target halts the machine, so execution cannot tell -8
    from -9; the shipped spelling is pinned as exact text.
    """
    from esolangs.runtime._evaluate import _evaluate

    table = "0111111010111101111010100000001100101100101110001110010110111110"
    program = boolean.addsubjump(table)
    assert program == (
        "338 338 4 333 338 -1 8 332 338 335 12 333 337 337 16 332 337 338 20 332 338 "
        "338 24 333 338 -1 28 332 338 335 32 333 337 337 36 332 337 338 40 332 338 33"
        "8 44 333 338 -1 48 332 338 335 52 333 337 337 56 332 337 338 60 332 338 338 "
        "64 333 338 -1 68 332 338 335 72 333 337 337 76 332 337 338 80 332 338 338 84"
        " 333 338 -1 88 332 338 335 92 333 337 337 96 332 337 338 100 332 338 338 104"
        " 333 338 -1 108 332 338 335 112 333 337 337 116 332 337 338 120 332 126 334 "
        "124 337 332 332 132 332 126 334 132 332 332 332 144 332 126 334 140 333 332 "
        "332 196 332 337 333 148 333 339 333 152 333 340 333 156 332 162 334 160 339 "
        "332 332 168 332 162 334 168 332 332 332 120 332 162 334 176 333 332 332 180 "
        "332 201 333 184 332 339 336 188 332 340 340 192 333 332 332 120 332 341 341 "
        "200 333 341 346 204 332 342 342 208 333 342 340 212 332 342 333 216 332 343 "
        "343 220 333 344 344 224 333 230 334 228 341 332 332 236 332 230 334 236 332 "
        "332 332 248 332 230 334 244 333 332 332 288 332 341 333 252 333 258 334 256 "
        "341 332 332 264 332 258 334 264 332 332 332 276 332 258 334 272 333 332 332 "
        "284 332 341 333 280 333 343 333 224 332 344 333 288 332 342 333 292 333 298 "
        "334 296 342 332 332 304 332 298 334 304 332 332 332 316 332 298 334 312 333 "
        "332 332 324 332 341 341 320 333 341 343 216 332 345 344 328 332 -1 345 -8 33"
        "2 0 1 4 48 6 0 0 6 0 0 0 0 0 48 62 53 59 21 0 19 19 7 39 54 7"
    )
    assert _evaluate("AddSubJump", program, inputs=6) == table


def test_five_input_all_essential_table_pins_its_balanced_size() -> None:
    """Every input essential at n=5: balancing weighs the default layout
    alone, never the legacy packed candidate; both sizes are pinned."""
    table = "00111001011001101010100000100011"
    assert len(esolangs.generate("AddSubJump", table)) == 993
    assert len(esolangs.generate("AddSubJump", table, balance=True)) == 1443
