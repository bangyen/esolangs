"""Befunge's folded header addresses the table below its steering rows."""

import math
import random
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.languages.befunge import generator as boolean
from esolangs.languages.befunge.generator import (
    _BOUND_NARROW,
    _BOUND_PACKED,
    _BOUND_WIDE,
    _min_columns,
    _plain_befunge,
    balance_befunge,
    befunge,
)
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.generator_support import (
    assert_saved_rows,
    constant_layouts,
    constant_runs,
)
from tests.support.witness_tables import row_bits


@pytest.mark.parametrize("inputs", [1, 4, 13])
# 80 builds what None does.
@pytest.mark.parametrize("width", [1, 5, None])
def test_befunge_folded_header_reads_the_table(inputs: int, width: int | None) -> None:
    rng = random.Random(inputs)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << inputs))
    program = esolangs.generate("Befunge", table, width=width).source
    lines = program.splitlines()
    floor = max(map(len, befunge(table, 1).splitlines()))
    assert max(map(len, lines)) <= max(80 if width is None else width, floor)
    assert max(map(len, lines)) <= 80
    assert len(lines) <= 25
    rows = (
        range(len(table))
        if inputs <= 5
        else [0, 1, 11, 27, len(table) // 2, len(table) - 2, len(table) - 1]
    )
    for row in rows:
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert run("Befunge", program, stdin=stdin).output.strip() == table[row]


def test_befunge_keeps_a_header_that_already_fits() -> None:
    _check_constants()
    table = "01101001"
    wide = befunge(table, 80)
    # The direct nibble lookup keeps its header over one data row.
    assert len(wide.splitlines()) == 2
    assert befunge(table, 5) != wide


@pytest.mark.medium
def test_befunge_default_uses_a_single_nibble_data_row() -> None:
    language = esolangs.Language("Befunge")
    for witness in construction_boundaries(language.name)[
        "natural_layout_to_nibble_cutoff"
    ]:
        table = witness.table()
        with patch.object(
            boolean, "_natural_befunge", wraps=boolean._natural_befunge
        ) as natural:
            artifact = language.generate(table)
        assert natural.call_count == int(witness.arity == 1)
        assert_saved_rows(language, artifact, table, range(len(table)))

    _check_one_row_nibbles()
    # Eight inputs use sixty-four four-bit cells below a straight header.
    rows = befunge(_seeded(8)).splitlines()
    assert len(rows) == 2
    assert max(map(len, rows)) == 64


def test_native_data_row_limit_switches_to_six_bit_packing() -> None:
    # One-row nibbles through eight essential inputs; n=9 needs general packing.
    assert befunge(_seeded(7)).count("\n") == 1
    assert not befunge(_seeded(7)).splitlines()[0].endswith("v")
    assert befunge(_seeded(9)).splitlines()[0].endswith("v")


@pytest.mark.parametrize("width", [None, 1])
def test_befunge_refuses_a_table_larger_than_the_torus(width: int | None) -> None:
    language = esolangs.Language("Befunge")
    admitted, refused = construction_boundaries("Befunge")["torus_input_cap"]
    table = admitted.table()
    artifact = language.generate(table, width=width)
    restored = language.load_program(language.dump_program(artifact))
    prepared = language.prepare(restored)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        result = prepared.evaluate(row_bits(row, admitted.arity))
        assert result.bit == table[row]
        assert result.observation.input_reads == admitted.arity
    with pytest.raises(esolangs.GeneratorCapError, match="at most thirteen inputs"):
        language.generate(refused.table(), width=width)


def test_single_digit_bound_reclaims_a_column() -> None:
    program = befunge("0110", 1)
    assert max(map(len, program.splitlines())) == 1
    assert len(program.splitlines()) <= 25


@pytest.mark.slow
@pytest.mark.parametrize("inputs", [11, 12, 13])
@pytest.mark.parametrize("width", [1, None])
def test_packed_ascii_lookup_answers_every_row(inputs: int, width: int | None) -> None:
    rng = random.Random(inputs)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << inputs))
    program = esolangs.generate("Befunge", table, width=width).source
    assert program.isascii()
    assert set(' "?@\\') <= set(program)
    for row, expected in enumerate(table):
        bits = [int(bit) for bit in f"{row:0{inputs}b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert (
            run("Befunge", program, stdin=stdin, max_steps=500).output.strip()
            == expected
        )


@pytest.mark.parametrize("inputs", [11, 12, 13])
@pytest.mark.parametrize("kind", ["zero", "one", "parity"])
def test_packed_ascii_lookup_controls_and_balance(inputs: int, kind: str) -> None:
    table = "".join(
        str(row.bit_count() % 2) if kind == "parity" else str(int(kind == "one"))
        for row in range(1 << inputs)
    )
    program = esolangs.generate("Befunge", table, balance=True).source
    assert program.isascii()
    assert len(program.splitlines()) <= 25
    assert max(map(len, program.splitlines())) <= 80
    for row in (0, 1, 5, 6, 479, 480, len(table) - 1):
        bits = [int(bit) for bit in f"{row:0{inputs}b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert (
            run("Befunge", program, stdin=stdin, max_steps=500).output.strip()
            == table[row]
        )


def test_width_one_and_balance_cross_the_packing_cutoff() -> None:
    for witness in construction_boundaries("Befunge")[
        "wide_parity_to_mandatory_packing"
    ]:
        n, table = witness.arity, witness.table()
        language = esolangs.Language("Befunge")
        for options in ({"width": 1}, {"balance": True}):
            artifact = language.generate(table, **options)
            # Parity can use a one-column sum through ten inputs only.
            assert (max(map(len, artifact.source.splitlines())) == 1) == (n == 10)
            restored = language.load_program(language.dump_program(artifact))
            prepared = language.prepare(restored)
            for row in (0, 5, 6, 479, 480, len(table) - 1):
                result = prepared.evaluate(row_bits(row, n))
                assert result.bit == table[row]


def test_befunge_balance_rejects_oversized_table() -> None:
    with pytest.raises(ValueError, match="at most thirteen inputs"):
        balance_befunge("0" * 16384, "")


def test_xor_has_one_column() -> None:
    xor = esolangs.generate("Befunge", "0110", width=1).source
    assert max(map(len, xor.splitlines())) == 1


@pytest.mark.parametrize("inputs", range(2, 14))
def test_balance_crossing_neighbours_match_the_wider_sweep(inputs: int) -> None:
    """Offsets -1..2 from the crossing tie the old -1..4 window on every layout."""
    table = _seeded(inputs)
    count = 1 << inputs
    layouts = [(5 * inputs + _BOUND_NARROW, 4, 9), (5 * inputs + _BOUND_WIDE, 10, 80)]
    if inputs > 10:
        count = (count + 5) // 6
        layouts = [(5 * inputs + _BOUND_PACKED, 10, 80)]
    for bound, low, high in layouts:
        floor = max(low, _min_columns(count, bound))
        if floor > high:
            continue
        side = math.isqrt(CELL_ASPECT * (count + bound) - 1) + 1

        found = [
            [
                balance_score(befunge(table, min(high, max(floor, side + off))))
                for off in offsets
            ]
            for offsets in (range(-1, 3), range(-1, 2 * CELL_ASPECT + 1))
        ]
        assert min(found[0]) == min(found[1])


def _seeded(inputs: int) -> str:
    rng = random.Random(inputs)
    return "".join(rng.choice("01") for _ in range(1 << inputs))


def _shape(program: str) -> tuple[int, int, int]:
    rows = program.splitlines()
    return len(program), len(rows), max(map(len, rows))


@pytest.mark.parametrize(
    ("inputs", "width", "shape"),
    [
        (1, 11, (5, 1, 5)),  # this seed is constant; no lookup header
        (4, 20, (79, 4, 20)),
        (7, 1, (170, 21, 8)),  # the packed row floor of the narrowest request
        (11, 1, (500, 21, 23)),  # the packed count's ceiling sets 23 columns
        (13, 1, (1522, 23, 67)),  # the packed lookup's row floor
    ],
)
def test_requested_width_builds_the_exact_grid(
    inputs: int, width: int, shape: tuple[int, int, int]
) -> None:
    program = esolangs.generate("Befunge", _seeded(inputs), width=width).source
    assert _shape(program) == shape


@pytest.mark.parametrize(
    ("table", "shape"),
    [
        ("1" * 16, (20, 3, 6)),
        ("0010001010001001", (78, 7, 14)),  # the crossing's side + 2 wins
        (_seeded(6), (130, 8, 16)),
        (_seeded(7), (143, 8, 19)),
        (_seeded(11), (484, 15, 32)),
    ],
)
def test_balanced_grid_is_the_smallest_square(
    table: str, shape: tuple[int, int, int]
) -> None:
    program = esolangs.generate("Befunge", table, balance=True).source
    assert _shape(program) == shape


def test_the_plain_build_never_exceeds_the_torus_width() -> None:
    # The _seeded(9) header is 81 cells: the fit check's cap at the
    # torus width sends it to the folded build (592 cells) instead of
    # emitting a row the 80-wide playfield would refuse.
    program = _plain_befunge(_seeded(9), "&\\2*+" * 9, 81)
    assert _shape(program) == (592, 8, 80)


def test_a_header_exactly_as_wide_as_the_request_stays_plain() -> None:
    # The native constant header is exactly 11 cells; equality stays plain.
    assert befunge("0" * 16, 11) == "&$&$&$&$0.@"


@pytest.mark.parametrize("width", [81, 1000])
def test_a_width_beyond_the_torus_still_fits_it(width: int) -> None:
    table = _seeded(11)
    program = esolangs.generate("Befunge", table, width=width).source
    assert max(map(len, program.splitlines())) <= 80
    for row in (0, 1, 2047):
        bits = [int(bit) for bit in f"{row:011b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert (
            run("Befunge", program, stdin=stdin, max_steps=500).output.strip()
            == table[row]
        )


def _check_constants() -> None:
    from esolangs.languages.befunge import generator

    assert not hasattr(generator, "MAX_INPUTS")
    from esolangs.languages.befunge.interpreter import _Machine

    for n in range(1, 14):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Befunge", bit * (1 << n), **options).source
                if not options:
                    assert len(program) == 2 * n + 3
                peak = 0
                for steps, written in constant_runs(
                    "Befunge",
                    lambda program, io: _Machine(program.splitlines(), io),
                    program,
                    n,
                    bit,
                    limit=1000,
                    token=True,
                    strip=True,
                ):
                    if not options:
                        assert steps == 2 * n + 3
                        assert (
                            written
                            <= 2 + (2 * n + 2).bit_length() + (2 * n - 1).bit_length()
                        )
                        peak = max(peak, written)
                if not options:
                    assert (
                        peak == 2 + (2 * n + 2).bit_length() + (2 * n - 1).bit_length()
                    )

            for source in constant_layouts(
                befunge, balance_befunge, bit * (1 << n)
            ).values():
                rows = source.splitlines()
                assert len(rows) <= 25
                assert max(map(len, rows)) <= 80


def _check_one_row_nibbles() -> None:
    from esolangs.languages.befunge.interpreter import _Machine
    from esolangs.languages.befunge.tests.ablations import ablate
    from scripts.docs.resource_evidence import resource_bounds

    bounds = resource_bounds("Befunge")
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula

    totals = [0, 0, 0]
    for value in range(256):
        table = f"{value:08b}"
        program = befunge(table)
        assert ablate(table, "default") == program
        baseline = ablate(table, "one_row_nibbles")
        totals[0] += len(baseline.splitlines()) * max(map(len, baseline.splitlines()))
        totals[1] += len(program.splitlines()) * max(map(len, program.splitlines()))
        for row in range(8):
            io = ScriptedIO(" ".join(f"{row:03b}") + " 7")
            machine = _Machine(program.splitlines(), io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            while not machine.halted:
                if io.getvalue():
                    assert io.reads == 3
                machine.step()
                written.sample(machine.workspace_snapshot())
                steps += 1
            assert io.getvalue().strip() == table[row]
            assert io.reads == 3
            assert io.past_end == 0
            assert io.input_num() == 7
            assert steps <= execution(3, program)
            assert written.bits <= workspace(3, program)
            totals[2] += steps
    assert totals == [21514, 11398, 45664]
    # A reversed selector exponent fails this asymmetric two-input function.
    program = befunge("0010")
    header, _data = program.split("\n")
    io = ScriptedIO("1 0")
    machine = _Machine([header, "$"], io)
    while not machine.halted:
        machine.step()
    assert io.getvalue().strip() != "1"


def test_packed_header_reserves_a_two_digit_offset() -> None:
    for width in (10, 11, 12, 13):
        table = "".join(str(row.bit_count() % 2) for row in range(256))
        program = befunge(table, width)
        assert len(program.splitlines()) <= 25
        for row, expected in enumerate(table):
            stdin = esolangs.encode_inputs("Befunge", list(map(int, f"{row:08b}")))
            assert run("Befunge", program, stdin=stdin).output.strip() == expected
