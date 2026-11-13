"""addsubjump generator tests."""

import random
from collections.abc import Iterator
from types import MappingProxyType

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import run
from esolangs.generation.helpers import in_input_order
from esolangs.languages.addsubjump import generator as boolean
from esolangs.languages.addsubjump.generator import (
    _addsubjump_ordered,
    _addsubjump_packed,
    _packed_build,
    addsubjump,
)
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from scripts.benchmark import WrittenState
from tests.generators.boolean_runners import _run_from, _runner
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_parity_at_most_doubles,
    constant_programs,
)
from tests.support.witness_tables import row_bits, witnesses

run_addsubjump = _runner("addsubjump")


def _full_packed(table: str) -> str:
    """The packed build over every input, ignored ones included."""
    return _packed_build(table, [1] * (len(table).bit_length() - 1))


def run_addsubjump_from(program: str, feed: Iterator[str]) -> str:
    """Run an AddSubJump program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.languages.addsubjump.interpreter", program, feed)


@pytest.mark.medium
def test_packed_projection_executes_every_three_input_table() -> None:
    for value in range(256):
        table = f"{value:08b}"
        program = _addsubjump_packed(table)
        legacy = _full_packed(table)
        assert len(program) <= len(legacy)
        assert _evaluate("AddSubJump", program, inputs=3) == table


@pytest.mark.medium
@pytest.mark.parametrize("kind", ["zero", "one", "first", "last", "ends"])
def test_wide_packed_projection_keeps_reads(kind) -> None:
    from esolangs.languages.addsubjump.interpreter import _Machine

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
    legacy = _full_packed(table)
    assert len(program) < len(legacy)
    assert _evaluate("AddSubJump", program, inputs=8) == table
    balanced = esolangs.generate("AddSubJump", table, balance=True).source
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
    used = [*range(essential - 1), 7]
    table = "".join(
        str(sum((row >> (7 - bit)) & 1 for bit in used) % 2) for row in range(256)
    )
    program = boolean.addsubjump(table)
    assert len(program) <= len(_full_packed(table))
    assert _evaluate("AddSubJump", program, inputs=8) == table


class TestAddSubJump:
    def test_branch_normalizes_ascii_bits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each ASCII input contributes its zero-or-one value to the index."""
        program = boolean.addsubjump("0110")
        assert "48" in program
        assert run_addsubjump(program, ["0", "1"]) == "1"
        assert run_addsubjump(program, ["1", "0"]) == "1"

        analyze = boolean._residual_ids

        def flipped_constants(table: str, n: int):
            diagram = analyze(table, n)
            return diagram._replace(
                constants=MappingProxyType(
                    {
                        key: None if value is None else 1 - value
                        for key, value in diagram.constants.items()
                    }
                )
            )

        monkeypatch.setattr(boolean, "_residual_ids", flipped_constants)
        damaged = _addsubjump_ordered("0110", (0, 1), shared=True)
        assert (
            "".join(
                run_addsubjump(damaged, [str(row >> 1), str(row & 1)])
                for row in range(4)
            )
            == "1001"
        )

    @pytest.mark.medium
    def test_all_three_input_tables(self) -> None:
        """The packed decoder executes the three-input witnesses."""
        for table in witnesses(3):
            program = boolean.addsubjump(table)
            for row in range(8):
                bits = [str((row >> shift) & 1) for shift in (2, 1, 0)]
                assert run_addsubjump(program, bits) == table[row]

    def test_three_input_total(self) -> None:
        """Shared residuals reduce the n=3 total from 105,924 to 96,030."""
        total = sum(len(boolean.addsubjump(f"{value:08b}")) for value in range(256))
        assert total == 96030

    def test_every_path_reads_each_input_once(self) -> None:
        """A run consumes exactly ``n`` inputs, whatever the table."""
        _check_native_constants()
        _check_packed_reader()
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
    assert totals[3] == (105924, 96030)
    assert totals[5] == (155006, 155006)
    assert totals[3][1] <= 0.95 * totals[3][0]


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 4, 6])
def test_sharing_boundaries(n: int) -> None:
    rng = random.Random(n)
    table = f"{rng.getrandbits(1 << n):0{1 << n}b}"
    program = addsubjump(table)
    assert len(program) <= len(_parent(table))
    for row, expected in enumerate(table):
        bits = [(row >> shift) & 1 for shift in reversed(range(n))]
        output = run(
            "AddSubJump",
            program,
            stdin=esolangs.encode_inputs("AddSubJump", bits),
            limits=esolangs.ExecutionLimits(execution_timeout=None),
        ).output
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
            output = run(
                "AddSubJump",
                program,
                stdin=esolangs.encode_inputs("AddSubJump", bits),
                limits=esolangs.ExecutionLimits(execution_timeout=None),
            ).output
            assert esolangs.read_answer("AddSubJump", output) == table[row]


def test_six_input_table_with_five_essential_rows_pins_both_sizes() -> None:
    """Five essential inputs at n=6 take the packed route; balancing weighs the
    default layout alone; both sizes are pinned."""
    table = "0010100100101001011011100110111010011011100110110110101101101011"
    assert len(esolangs.generate("AddSubJump", table).source) == 793
    assert len(esolangs.generate("AddSubJump", table, balance=True).source) == 1429


def test_packed_program_prints_then_halts_on_the_special_address() -> None:
    """The packed builder's last instruction prints, then jumps to -8.

    Any negative target halts the machine, so execution cannot tell -8
    from -9; the shipped spelling is pinned as exact text.
    """
    table = "0111111010111101111010100000001100101100101110001110010110111110"
    program = boolean.addsubjump(table)
    assert program == (
        "7 7 12 7 1 4 3024 0 0 48 0 0 8 8 16 7 8 -1 20 7 8 8 24 7 8 -1 28 7 8 8 32 7 "
        "8 -1 36 7 8 8 40 7 8 -1 44 7 8 8 48 7 8 -1 52 7 8 8 56 7 8 -1 60 7 8 6 64 4 "
        "70 5 68 8 7 7 76 7 70 5 76 7 7 7 88 7 70 5 84 4 7 7 140 7 8 4 92 4 277 4 96 "
        "4 278 4 100 7 106 5 104 277 7 7 112 7 106 5 112 7 7 7 64 7 106 5 120 4 7 7 1"
        "24 7 145 4 128 7 277 276 132 7 278 278 136 4 7 7 64 7 279 279 144 4 279 283 "
        "148 7 280 280 152 4 280 278 156 7 280 4 160 7 281 281 164 4 282 282 168 4 17"
        "4 5 172 279 7 7 180 7 174 5 180 7 7 7 192 7 174 5 188 4 7 7 232 7 279 4 196 "
        "4 202 5 200 279 7 7 208 7 202 5 208 7 7 7 220 7 202 5 216 4 7 7 228 7 279 4 "
        "224 4 281 4 168 7 282 4 232 7 280 4 236 4 242 5 240 280 7 7 248 7 242 5 248 "
        "7 7 7 260 7 242 5 256 4 7 7 268 7 279 279 264 4 279 281 160 7 9 282 272 7 -1"
        " 9 -8 7 6 6 0 0 0 0 0 62 53 59 21 0 19 19 7 39 54 7"
    )
    assert _evaluate("AddSubJump", program, inputs=6) == table


def test_five_input_all_essential_table_pins_its_balanced_size() -> None:
    """Every input essential at n=5: balancing weighs the default layout
    alone, never the legacy packed candidate; both sizes are pinned."""
    table = "00111001011001101010100000100011"
    assert len(esolangs.generate("AddSubJump", table).source) == 775
    assert len(esolangs.generate("AddSubJump", table, balance=True).source) == 1409


def _check_native_constants() -> None:
    from esolangs.languages.addsubjump.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("AddSubJump")["workspace"].formula

    for n, bit, _options, program in constant_programs("AddSubJump", range(1, 13)):
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("AddSubJump", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "Q", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = count_steps(machine, n + 1, written=written)
            assert steps == n + 1
            assert written.bits == workspace(n, program)
            assert io.getvalue() == bit
            assert io.input_char() == ord("Q")


def _check_packed_reader() -> None:
    """Raw Horner reads preserve projection, stream order and low data words."""
    from esolangs.languages.addsubjump.interpreter import _Machine

    for position in range(6):
        table = "".join(str((row >> (5 - position)) & 1) for row in range(64))
        for program in (
            _addsubjump_packed(table),
            esolangs.generate("AddSubJump", table, width=1).source,
            esolangs.generate("AddSubJump", table, balance=True).source,
        ):
            for row in (0, 21, 42, 63):
                io = ReadFirstIO(f"{row:06b}" + "Q", expected=6)
                machine = _Machine(program, io)
                for _ in range(100_000):
                    if machine.halted:
                        break
                    machine.step()
                assert machine.halted
                assert io.reads == 6
                assert io.past_end == 0
                assert io.getvalue() == table[row]
                assert io.input_char() == ord("Q")
