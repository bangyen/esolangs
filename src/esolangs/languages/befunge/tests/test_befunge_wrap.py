"""Befunge's folded header addresses the table below its steering rows."""

import math
import random

import pytest

import esolangs
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.languages.befunge.generator import (
    _BOUND_NARROW,
    _BOUND_PACKED,
    _BOUND_WIDE,
    _min_columns,
    _plain_befunge,
    balance_befunge,
    befunge,
)


@pytest.mark.parametrize("inputs", [1, 4, 13])
# 80 builds what None does.
@pytest.mark.parametrize("width", [1, 5, None])
def test_befunge_folded_header_reads_the_table(inputs: int, width: int | None) -> None:
    rng = random.Random(inputs)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << inputs))
    program = esolangs.generate("Befunge", table, width=width)
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
        assert esolangs.run("Befunge", program, stdin=stdin).strip() == table[row]


def test_befunge_keeps_a_header_that_already_fits() -> None:
    _check_constants()
    table = "01101001"
    wide = befunge(table, 80)
    # The natural build: one header row over the 4-wide table, unfolded.
    assert len(wide.splitlines()) == 3
    assert befunge(table, 5) != wide


def test_befunge_default_lays_the_table_at_the_grid_width() -> None:
    # Candidate 20: the default path no longer tries the sqrt width.  From
    # n=8 the packed grid wins the area race: two header rows, 43 data cells.
    rows = befunge(_seeded(8)).splitlines()
    assert len(rows) == 3
    assert max(map(len, rows)) == 80


def test_the_packed_grid_wins_only_when_it_is_smaller() -> None:
    # n=7 ties (240 cells each), so the plain build stays; n=9 packs.
    assert befunge(_seeded(7)).count("\n") == 2
    assert not befunge(_seeded(7)).splitlines()[0].endswith("v")
    assert befunge(_seeded(9)).splitlines()[0].endswith("v")


@pytest.mark.parametrize("width", [None, 1, 80, 1000])
def test_befunge_refuses_a_table_larger_than_the_torus(width: int | None) -> None:
    with pytest.raises(ValueError, match="at most thirteen inputs"):
        befunge("01" * 8192, width)


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
    program = esolangs.generate("Befunge", table, width=width)
    assert program.isascii()
    assert set(' "?@\\') <= set(program)
    for row, expected in enumerate(table):
        bits = [int(bit) for bit in f"{row:0{inputs}b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert (
            esolangs.run("Befunge", program, stdin=stdin, max_steps=500).strip()
            == expected
        )


@pytest.mark.parametrize("inputs", [11, 12, 13])
@pytest.mark.parametrize("kind", ["zero", "one", "parity"])
def test_packed_ascii_lookup_controls_and_balance(inputs: int, kind: str) -> None:
    table = "".join(
        str(row.bit_count() % 2) if kind == "parity" else str(int(kind == "one"))
        for row in range(1 << inputs)
    )
    program = esolangs.generate("Befunge", table, balance=True)
    assert program.isascii()
    assert len(program.splitlines()) <= 25
    assert max(map(len, program.splitlines())) <= 80
    for row in (0, 1, 5, 6, 479, 480, len(table) - 1):
        bits = [int(bit) for bit in f"{row:0{inputs}b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert (
            esolangs.run("Befunge", program, stdin=stdin, max_steps=500).strip()
            == table[row]
        )


def test_befunge_balance_rejects_oversized_table() -> None:
    with pytest.raises(ValueError, match="at most thirteen inputs"):
        balance_befunge("0" * 16384, "")


def test_xor_has_one_column() -> None:
    xor = esolangs.generate("Befunge", "0110", width=1)
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
        (7, 1, (169, 20, 8)),  # the packed row floor of the narrowest request
        (11, 1, (500, 21, 23)),  # the packed count's ceiling sets 23 columns
        (13, 1, (1522, 23, 67)),  # the packed lookup's row floor
    ],
)
def test_requested_width_builds_the_exact_grid(
    inputs: int, width: int, shape: tuple[int, int, int]
) -> None:
    program = esolangs.generate("Befunge", _seeded(inputs), width=width)
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
    program = esolangs.generate("Befunge", table, balance=True)
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
    program = esolangs.generate("Befunge", table, width=width)
    assert max(map(len, program.splitlines())) <= 80
    for row in (0, 1, 2047):
        bits = [int(bit) for bit in f"{row:011b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert (
            esolangs.run("Befunge", program, stdin=stdin, max_steps=500).strip()
            == table[row]
        )


def _check_constants() -> None:
    from esolangs.languages.befunge.interpreter import _Machine
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 14):

        class ReadFirstIO(ScriptedIO):
            expected = n

            def _write(self, value):
                assert self.reads == self.expected
                super()._write(value)

        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Befunge", bit * (1 << n), **options)
                if not options:
                    assert len(program) == 2 * n + 3
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    stdin = esolangs.encode_inputs(
                        "Befunge", list(map(int, f"{row:0{n}b}"))
                    )
                    io = ReadFirstIO(stdin + "\n7\n")
                    machine = _Machine(program.splitlines(), io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                        assert steps < 1000
                    assert io.getvalue().strip() == bit
                    assert io.past_end == 0
                    assert io.input_num() == 7
                    if not options:
                        assert steps == 2 * n + 3
                        assert (
                            written.bits
                            <= 2 + (2 * n + 2).bit_length() + (2 * n - 1).bit_length()
                        )
                        peak = max(peak, written.bits)
                if not options:
                    assert (
                        peak == 2 + (2 * n + 2).bit_length() + (2 * n - 1).bit_length()
                    )

            default = befunge(bit * (1 << n))
            assert befunge(bit * (1 << n), len(default)) == default
            balanced = balance_befunge(bit * (1 << n), default)
            oracle = min(
                (
                    befunge(bit * (1 << n), width)
                    for width in range(1, len(default) + 1)
                ),
                key=balance_score,
            )
            assert balance_score(balanced) == balance_score(oracle)
            for width in range(1, len(default) + 1):
                rows = befunge(bit * (1 << n), width).splitlines()
                assert len(rows) <= 25
                assert max(map(len, rows)) <= 80
