"""Piet's linear Boolean generator."""

import random
from itertools import pairwise, product

import pytest

import esolangs
from esolangs.generation.helpers import essential_inputs, read_at
from esolangs.generation.raster_lookup.balance import _bounded_operations
from esolangs.languages.piet.generator import piet as generate
from esolangs.languages.piet.tests.test_boolean_piet_raster_balance import TABLES, score
from esolangs.raster import Raster
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO


@pytest.mark.parametrize(
    "truth_table",
    ["01", "0110", "10010110", "0110100110010110"],
)
def test_every_row_executes(truth_table: str) -> None:
    program = generate(truth_table)
    inputs = len(truth_table).bit_length() - 1
    for bits in product((0, 1), repeat=inputs):
        stdin = "".join(f"{bit}\n" for bit in bits)
        row = int("".join(map(str, bits)), 2) if bits else 0
        assert esolangs.run("Piet", program, stdin=stdin) == truth_table[row]


def test_the_generator_scale_upscales_and_executes() -> None:
    plain, scaled = generate("0110"), generate("0110", scale=3)
    assert len(scaled.rows) == 3 * len(plain.rows)
    assert len(scaled.rows[0]) == 3 * len(plain.rows[0])
    for row, bits in enumerate(product((0, 1), repeat=2)):
        stdin = "".join(f"{bit}\n" for bit in bits)
        assert esolangs.run("Piet", scaled, stdin=stdin) == "0110"[row]


@pytest.mark.parametrize("balanced", [False, True])
def test_and_uses_two_reads_multiply_and_output(*, balanced: bool) -> None:
    program = esolangs.generate("Piet", "0001", balance=balanced)
    assert isinstance(program, Raster)
    assert (len(program.rows[0]), len(program.rows)) == (6, 3)
    assert _evaluate("Piet", Raster.from_png(program.to_png()), inputs=2) == "0001"


@pytest.mark.parametrize("table", ["0001", "0010", "0100", "1000", "1110"])
@pytest.mark.parametrize("width", [None, 13])
def test_literal_product_keeps_ignored_inputs(table: str, width: int | None) -> None:
    for expanded in (
        table + table,
        "".join(bit * 2 for bit in table),
        "".join(table[start : start + 2] * 2 for start in (0, 2)),
    ):
        program = generate(expanded, width=width)
        assert (
            _evaluate("Piet", Raster.from_png(program.to_png()), inputs=3) == expanded
        )


@pytest.mark.medium
def test_every_three_input_function_executes_through_png() -> None:
    _check_constants()
    _check_majority()
    _check_triples()
    total = 0
    for encoded in range(256):
        truth_table = f"{encoded:08b}"
        program = Raster.from_png(generate(truth_table).to_png())
        pixels = sum(map(len, program.rows))
        essential = essential_inputs(truth_table, 3)
        reduced = read_at(truth_table, essential, 3)
        parent_width = (
            18
            + 2 * len(reduced)
            + reduced.count("0")
            + 5 * len(essential)
            + 2 * (3 - len(essential))
        )
        assert pixels <= 3 * parent_width
        total += pixels
        for row in range(8):
            stdin = "".join(f"{bit}\n" for bit in f"{row:03b}")
            assert esolangs.run("Piet", program, stdin=stdin) == truth_table[row]
    # Parent table lookup emitted 38,997 codels over this exhaustive corpus.
    # The halved lookup (retired 2026-10-28) held this at 34,062; storing the
    # complement past half zeros brings it to 33,882.
    # Majority and its complement now count their inputs.
    assert total == 33_633


@pytest.mark.slow
def test_larger_functions_execute_through_png() -> None:
    rng = random.Random(20261001)
    for inputs in (4, 5, 6):
        tables = [
            "".join(rng.choice("01") for _ in range(2**inputs)) for _ in range(12)
        ]
        for row in (0, 2**inputs - 1, 2**inputs // 3):
            table = "".join(str(int(i == row)) for i in range(2**inputs))
            tables.extend((table, table.translate(str.maketrans("01", "10"))))
        for table in tables:
            for balanced in (False, True):
                image = esolangs.generate("Piet", table, balance=balanced)
                decoded = Raster.from_png(image.to_png())
                assert _evaluate("Piet", decoded, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("balanced", [False, True])
def test_larger_asymmetric_function_executes_through_png(*, balanced: bool) -> None:
    table = "".join(str(int(row in (0, 7, 31, 63))) for row in range(64))
    image = esolangs.generate("Piet", table, balance=balanced)
    assert _evaluate("Piet", Raster.from_png(image.to_png()), inputs=6) == table


def test_emitted_pixels_are_linear_in_the_table() -> None:
    for inputs in range(1, 9):
        entries = 2**inputs
        program = generate("01" * (entries // 2) if entries > 1 else "0")
        assert len(program.rows) * len(program.rows[0]) <= 64 * entries
        assert len(program.to_png()) <= 110 * entries


def test_ignored_inputs_are_read_but_not_indexed() -> None:
    """An ignored input costs its read and a pop, never table entries."""
    widths = [len(generate("0" * 2**inputs).rows[0]) for inputs in range(1, 9)]
    assert [b - a for a, b in pairwise(widths)] == [2] * 7
    # The second input is ignored: the stored table is the one-input one.
    assert len(generate("0011").rows[0]) == len(generate("01").rows[0]) + 2
    assert esolangs.run("Piet", generate("0" * 8), stdin="1\n1\n1\n") == "0"


def _codels(program: Raster) -> int:
    """The area, which is what the default minimises."""
    return len(program.rows) * len(program.rows[0])


def test_retained_lookup_is_the_smaller_of_strip_and_fold() -> None:
    """The strip wins a tie, a fold only by strictly less area; folds from n=5."""
    from esolangs.languages.piet.generator import _generate, _smallest

    rng = random.Random(11)
    for bits in (2, 4, 5, 6):
        table = "".join(rng.choice("01") for _ in range(1 << bits))
        flat, chosen = _generate(table), _smallest(table)
        assert chosen is flat or _codels(chosen) < _codels(flat)
        if bits >= 5:
            assert _codels(chosen) < _codels(flat)
        assert _evaluate("Piet", chosen, inputs=bits) == table


def test_a_tied_retained_pack_loses_to_the_strip() -> None:
    """This n=4 table's least packed layout ties the strip's area exactly.

    The seeded tables in the race test above contain no tie, so the
    strip-wins-a-tie rule needs this witness: at equal area the
    default must be the strip itself, not the packed layout.
    """
    from esolangs.languages.piet.generator import _generate, _smallest

    table = "1111000111100010"
    assert _smallest(table).rows == _generate(table).rows
    assert _evaluate("Piet", generate(table), inputs=4) == table


def test_constant_half_tables_run() -> None:
    """All four constant-half shapes at n=6 execute."""
    rng = random.Random(3)
    half = "".join(rng.choice("01") for _ in range(32))
    for table in (half + "0" * 32, half + "1" * 32, "0" * 32 + half, "1" * 32 + half):
        assert _evaluate("Piet", generate(table), inputs=6) == table


@pytest.mark.parametrize("truth_table", ["", "0", "1", "010", "0121"])
def test_invalid_truth_table_is_rejected(truth_table: str) -> None:
    with pytest.raises(ValueError, match="truth table"):
        generate(truth_table)


def test_balance_raster_retains_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace

    from esolangs.registry import LANGUAGES

    monkeypatch.setitem(
        LANGUAGES,
        "Piet",
        replace(
            LANGUAGES["Piet"], backend=replace(LANGUAGES["Piet"].backend, balance=None)
        ),
    )
    default = esolangs.generate("Piet", "0110")
    balanced = esolangs.generate("Piet", "0110", balance=True)
    assert isinstance(default, esolangs.Raster)
    assert isinstance(balanced, esolangs.Raster)
    assert balanced.to_png() == default.to_png()


@pytest.mark.medium
@pytest.mark.parametrize("table", [*TABLES, "10010110", "00000001", "01011010"])
def test_piet_balance_matches_rendered_width_oracle(table: str) -> None:
    operations = _bounded_operations(table)
    candidates = [esolangs.generate("Piet", table)]
    for width in range(13, sum(op.size for op in operations) + 7):
        image = esolangs.generate("Piet", table, width=width)
        assert isinstance(image, Raster)
        candidates.append(image)
        assert (
            esolangs.run(
                "Piet",
                Raster.from_png(image.to_png()),
                stdin="0\n" * (len(table).bit_length() - 1),
            )
            == table[0]
        )
    balanced = esolangs.generate("Piet", table, balance=True)
    assert isinstance(balanced, Raster)
    old = min(candidates, key=score)
    assert score(balanced) <= score(old) or score(balanced)[1] < score(old)[1]
    assert (
        _evaluate(
            "Piet",
            Raster.from_png(balanced.to_png()),
            inputs=len(table).bit_length() - 1,
        )
        == table
    )


@pytest.mark.medium
def test_piet_keeps_an_already_better_layout() -> None:
    from esolangs.generation.raster_lookup.balance import balance

    source = esolangs.generate("Piet", "0001", balance=True)
    assert isinstance(source, Raster)
    assert balance("0001", source) is source
    assert _evaluate("Piet", Raster.from_png(source.to_png()), inputs=2) == "0001"


@pytest.mark.medium
def test_compact_folds_execute_without_growing() -> None:
    from esolangs.generation.raster_lookup.balance import _balanced_plan

    total = 0
    for inputs in range(1, 4):
        for encoded in range(2 ** (2**inputs)):
            table = f"{encoded:0{2**inputs}b}"
            default = generate(table)
            old = _balanced_plan(_bounded_operations(table), default, compact=False)
            ceiling = min(old.score(), score(default))[1]
            image = esolangs.generate("Piet", table, balance=True)
            assert score(image)[1] <= ceiling
            assert (
                _evaluate("Piet", Raster.from_png(image.to_png()), inputs=inputs)
                == table
            )
            if inputs == 3:
                total += score(image)[1]
    # 40,868 under |width - height| first; max(width, height) first: 40,574.
    # The sum form and complemented lookup (2026-10-28): 40,256.
    assert total == 39_965


@pytest.mark.parametrize("width", [13, 19, 30])
def test_compact_turns_and_halt_execute(width: int) -> None:
    table = "00010111"
    image = esolangs.generate("Piet", table, width=width)
    assert _evaluate("Piet", Raster.from_png(image.to_png()), inputs=3) == table


def test_compact_majority_is_smaller() -> None:
    image = esolangs.generate("Piet", "00010111", balance=True)
    assert (len(image.rows[0]), len(image.rows)) == (13, 3)


def _check_majority() -> None:
    from esolangs.languages.piet.interpreter import _Machine
    from esolangs.languages.piet.tests.formulas import _codels, _steps, _written
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(3, 9):
        for inverted in (False, True):
            table = "".join(
                str(int((row.bit_count() > n // 2) ^ inverted)) for row in range(1 << n)
            )
            for options in ({}, {"width": 13}, {"balance": True}, {"scale": 3}):
                image = esolangs.generate("Piet", table, **options)
                assert isinstance(image, Raster)
                image = Raster.from_png(image.to_png())
                scale = 3 if options == {"scale": 3} else 1
                for row in (0, 1, (1 << n) // 3, (1 << n) - 1):
                    io = ReadFirstIO("\n".join(f"{row:0{n}b}") + "\n7\n", expected=n)
                    machine = _Machine(image, io, scale=scale)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps < 10_000
                    assert io.getvalue() == table[row]
                    assert io.reads == n
                    assert io.past_end == 0
                    assert io.input_token() == "7"
                    if not options:
                        assert len(image.rows) * len(image.rows[0]) <= _codels(n, "")
                        assert steps <= _steps(n, "")
                        assert written.bits <= _written(n, "")
    # Ignored reads before, between and after the five essential positions.
    selected = (1, 2, 4, 6, 7)
    table = "".join(
        str(int(sum((row >> (8 - i)) & 1 for i in selected) > 2)) for row in range(512)
    )
    for options in ({}, {"width": 13}, {"balance": True}):
        image = esolangs.generate("Piet", table, **options)
        assert isinstance(image, Raster)
        for row in (0, 1, 170, 511):

            class ProjectedIO(ScriptedIO):
                def _write(self, value):
                    assert self.reads == 9
                    super()._write(value)

            io = ProjectedIO("\n".join(f"{row:09b}") + "\n7\n")
            machine = _Machine(image, io, scale=1)
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
                assert steps < 10_000
            assert io.getvalue() == table[row]
            assert io.reads == 9
            assert io.past_end == 0
            assert io.input_token() == "7"


def _check_constants() -> None:
    from esolangs.languages.piet.interpreter import _Machine
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Piet", bit * (1 << n), **options)
                if not options:
                    assert len(program.rows) * len(
                        program.rows[0]
                    ) <= 6 * n + 12 - 3 * int(bit)
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Piet", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "\n7\n", expected=n)
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps < 1000
                    assert io.getvalue() == bit
                    assert io.past_end == 0
                    assert io.input_num() == 7
                    if not options:
                        assert steps == 2 * n + 3 - int(bit)
                        assert (
                            written.bits
                            <= 4
                            + (2 * n + 3 - int(bit)).bit_length()
                            + (2 * n - 1).bit_length()
                            + n.bit_length()
                        )
                        peak = max(peak, written.bits)
                if not options:
                    assert (
                        peak
                        == 4
                        + (2 * n + 3 - int(bit)).bit_length()
                        + (2 * n - 1).bit_length()
                        + n.bit_length()
                    )

                if not options:
                    scaled = esolangs.generate("Piet", bit * (1 << n), scale=3)
                    assert len(scaled.rows) == 3 * len(program.rows)
                    assert len(scaled.rows[0]) == 3 * len(program.rows[0])
                    assert esolangs.run("Piet", scaled, stdin="1\n" * n) == bit


def _check_triples() -> None:
    """Exercise the command-admitted strip, polarity and ignored-input layouts."""
    from esolangs.languages.piet.generator import _INITIAL, _chunks, _next_colour, strip
    from esolangs.languages.piet.interpreter import _Machine
    from esolangs.languages.piet.tests.formulas import (
        _codels as bound_area,
    )
    from esolangs.languages.piet.tests.formulas import (
        _steps,
        _written,
    )
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in (7, 8):
        rng = random.Random(184700 + n)
        table = "".join(rng.choice("01") for _ in range(1 << n))
        cases = [table, table.translate(str.maketrans("01", "10"))]
        if n == 8:
            cases.append("".join(table[row & 127] for row in range(256)))
        for truth_table in cases:
            for options in ({}, {"width": 15}, {"balance": True}):
                image = esolangs.generate("Piet", truth_table, **options)
                assert isinstance(image, Raster)
                image = Raster.from_png(image.to_png())
                for row in (0, (1 << n) // 3, (1 << n) - 1):
                    io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\n7\n")
                    machine = _Machine(image, io, scale=1)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps < 10_000
                    assert io.getvalue() == truth_table[row]
                    assert io.reads == n
                    assert io.past_end == 0
                    assert io.input_token() == "7"
                    if not options:
                        assert _codels(image) <= bound_area(n, "")
                        assert steps <= _steps(n, "")
                        assert written.bits <= _written(n, "")
    # The divisor is essential: modulo3 cannot decode three packed bits.
    table = "00110110"
    operations = _chunks(table, [0, 1, 2], 3, flip=False)
    good = strip(operations, _INITIAL, _next_colour)
    assert _evaluate("Piet", good, inputs=3) == table
