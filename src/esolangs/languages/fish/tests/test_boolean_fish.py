"""Executed tests for the Fish boolean generator."""

import random
from itertools import pairwise

import pytest

import esolangs
from esolangs import run as execute
from esolangs.generation.helpers import input_weights
from esolangs.generation.wrap import balance_score
from esolangs.languages.fish.generator import (
    _column,
    _folded,
    _packed,
    _packed_folded,
    balance_fish,
    fish,
)
from esolangs.languages.fish.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.evaluation import _evaluate
from tests.support.generator_support import (
    assert_saved_rows,
    constant_layouts,
    constant_runs,
    run_lines,
)
from tests.support.witness_tables import witnesses


def _fish_tables():
    return [table for inputs in (1, 6) for table in witnesses(inputs)]


def _run(table: str, row: int, width: int | None = None) -> tuple[str, int]:
    bits = f"{row:0{len(table).bit_length() - 1}b}"
    return run_lines(run, fish(table, width), bits)


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 3, 4, 7, 13, 40])
def test_folded_lookup_executes_every_three_input_table(width: int) -> None:
    for table in witnesses(3):
        program = fish(table, width)
        assert max(map(len, program.split("\n"))) <= max(3, width)
        for row, expected in enumerate(table):
            assert _run(table, row, width) == (expected, 3)


def test_source_growth_is_linear_in_the_table() -> None:
    # One-input "01" is parity, which takes the one-column program.
    sizes = [len(fish("01" * (1 << (n - 1)))) for n in range(2, 13)]
    assert all(right <= 2 * left for left, right in pairwise(sizes))


@pytest.mark.parametrize("width", [None, 1, 3, 40])
def test_parity_uses_the_column_at_every_width(width: int | None) -> None:
    for n in (1, 4, 10):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        for bits in (table, table.translate(str.maketrans("01", "10"))):
            program = fish(bits, width)
            assert max(map(len, program.splitlines())) == 1
            assert len(program.splitlines()) == 2 * n + 4 + (bits[0] == "1") * 2
            assert _evaluate("Fish", program, inputs=n) == bits


@pytest.mark.medium
@pytest.mark.parametrize("table", _fish_tables())
def test_fish_balance_matches_all_power_of_two_folds(table) -> None:
    default = fish(table)
    balanced = balance_fish(table, default)
    n = len(table).bit_length() - 1
    weights, reduced = input_weights(table, n)
    reads = "".join("i68*-$2*+" if weight else "i~" for weight in weights)
    # Folds run past the table's width: it then sits in one row.
    layouts = [default, fish(table, 1)] + [
        _folded(reads, reduced, 1 << exponent)
        for exponent in range(len(reads).bit_length() + 1)
    ]
    # The packed row folds at any width; four of them are balance's candidates.
    assert balance_score(balanced) <= min(map(balance_score, layouts))
    layouts += [_packed_folded(reads, reduced, columns) for columns in range(4, 65)]
    optimum = min(layouts, key=balance_score)
    assert balance_score(balanced)[0] <= 1.05 * balance_score(optimum)[0]
    assert esolangs.generate("Fish", table, balance=True).source == balanced
    assert _evaluate("Fish", balanced, inputs=len(table).bit_length() - 1) == table


def test_xor_has_one_column() -> None:
    xor = esolangs.generate("Fish", "0110", width=1).source
    assert max(map(len, xor.splitlines())) == 1


@pytest.mark.slow
def test_a_balanced_table_past_225_code_rows_uses_a_doubling_height_literal() -> None:
    """n=23 balanced needs more than a*b rows of code; the doubling literal answers."""
    inputs = 23
    table = format(random.Random(2).getrandbits(1 << inputs), f"0{1 << inputs}b")
    program = esolangs.generate("Fish", table, balance=True).source
    for row in (0, 5000001, (1 << inputs) - 1):
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Fish", bits)
        got = execute(
            "Fish",
            program,
            stdin=stdin,
            limits=esolangs.ExecutionLimits(execution_timeout=60),
        ).output
        assert esolangs.read_answer("Fish", got) == table[row], row


def test_packed_programs_execute_seeded_random_tables(monkeypatch) -> None:
    # The witness tables' packed forms lose the race or cancel out; a
    # plain random table's packed row is decoded against _BASE and the
    # complemented bits, and both must hold.
    rng = random.Random(20261024)
    for n in (4, 5, 6):
        for _ in range(3):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            assert _evaluate("Fish", fish(table), inputs=n) == table
    _check_precision_guards(monkeypatch)


def test_a_width_that_exactly_fits_the_header_returns_the_plain_program() -> None:
    # The native constant is exactly seven cells; equality keeps the row.
    assert fish("0000", 7) == "i~i~0n;"


def test_fold_columns_fill_all_but_two_of_the_width() -> None:
    # Width 4 folds on two columns; one less margin folds on one.
    assert fish("0001", 4) == (
        ">0iv\nv86<\n>*-v\nv2$<\n>*+v\nv6i<\n>8*v\nv$-<\n>2*v\nv:+<\n"
        ">12v\nv%*<\n>$:v\nv21<\n>*%v\nv1-<\n>2*v\nv5,<\n>5*v\nvg+<\n"
        ">68v\nv-*<\n>n;v\n\n\n00\n01"
    )


def test_the_fold_height_reserve_counts_three_literal_cells() -> None:
    # rows_for(3): the a*b literal is three cells, and the height it
    # buys must cover the code exactly as reserved.
    assert fish("01010000", 1) == (
        ">0v\nvi<\n>6v\nv8<\n>*v\nv-<\n>$v\nv2<\n>*v\nv+<\n>iv\nv~<\n"
        ">iv\nv6<\n>8v\nv*<\n>-v\nv$<\n>2v\nv*<\n>+v\nv:<\n>1v\nv%<\n"
        ">$v\nv:<\n>1v\nv%<\n>-v\nv1<\n>,v\nv7<\n>6v\nv*<\n>+v\nvg<\n"
        ">6v\nv8<\n>*v\nv-<\n>nv\nv;<\n0\n1\n0\n0"
    )


def test_a_constant_uses_one_column_when_narrow() -> None:
    language = esolangs.Language("Fish")
    for witness in construction_boundaries(language.name)[
        "constant_vertical_to_fold_floor"
    ]:
        table = witness.table()
        for width, first_row in ((2, "v"), (3, ">iv")):
            artifact = language.generate(table, width=width)
            assert artifact.source.splitlines()[0] == first_row
            assert_saved_rows(language, artifact, table, range(len(table)))

    _check_constants()
    assert fish("00", 1) == "v\ni\n~\n0\nn\n;"


def test_the_column_literal_caps_at_225_then_doubles() -> None:
    # f*k reaches 225 in three cells; the next column is a power of two.
    assert _column(211) == (225, "ff*")
    assert _column(225) == (225, "ff*")
    assert _column(226) == (256, "12*2*2*2*2*2*2*2*")


def test_the_packed_overlap_check_reserves_two_literals() -> None:
    # The literal appears twice; when both copies would overrun the
    # column the powers start at, the column moves past them.
    powers = "".join(chr(64 + (1 << bit)) for bit in range(6))
    snug = _packed("r" * 185, "0" * 16)
    assert snug.index(powers) == 256
    assert len(snug) == 265
    wide = _packed("r" * 186, "0" * 16)
    assert wide.index(powers) == 512
    assert len(wide) == 521


def test_the_fold_height_past_225_doubles_from_the_body_length() -> None:
    # 226 rows of code: too many for an a*b literal (cap 225), so the
    # height doubles to 512 and the literal spells it with 2* nine times.
    rows = _folded("r" * 204, "01" * 128, 1).split("\n")
    assert len(rows) == 768
    assert rows.count("") == 270


@pytest.mark.parametrize(("n", "side"), [(7, 18), (8, 18)])
def test_balance_folds_the_packed_row(n: int, side: int) -> None:
    """Seed n: the packed row folded (an unpacked fold gave side 30 / 34)."""
    table = format(random.Random(n).getrandbits(1 << n), f"0{1 << n}b")
    balanced = esolangs.generate("Fish", table, balance=True).source
    assert balance_score(balanced)[0] == side
    assert _evaluate("Fish", balanced, inputs=n) == table
    wrong = table[:-1] + str(1 - int(table[-1]))
    assert _evaluate("Fish", balanced, inputs=n) != wrong


def _check_constants() -> None:
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Fish", bit * (1 << n), **options).source
                if not options:
                    assert len(program) == 2 * n + 3
                for steps, written in constant_runs(
                    "Fish",
                    lambda program, io: _Machine(program.splitlines(), io),
                    program,
                    n,
                    bit,
                    limit=2000,
                    token=False,
                    strip=False,
                ):
                    if not options:
                        assert steps == 2 * n + 3
                        assert written <= 7 + (2 * n + 3).bit_length() + n.bit_length()

            for width, source in constant_layouts(
                fish, balance_fish, bit * (1 << n)
            ).items():
                assert max(map(len, source.splitlines())) <= width


def _check_precision_guards(monkeypatch) -> None:
    from esolangs.languages.fish import generator
    from esolangs.languages.fish.generator import _integer_coordinates

    # Force every precision fallback on small tables, including ignored bits.
    monkeypatch.setattr(generator, "_EXACT", 0)
    for table in ("00110110", "01011010", "00000001", "11111110"):
        for options in ({}, {"balance": True}, {"width": 1}, {"width": 3}):
            program = esolangs.generate("Fish", table, **options).source
            assert _evaluate("Fish", program, inputs=3) == table
    # Logical large addresses need only the coordinate prefix, not a huge table.
    for n, columns, row in (
        (53, 1, (1 << 53) - 1),
        (108, 1 << 54, (1 << 108) - 1),
    ):
        prefix = _integer_coordinates("i68*-$2*+" * n, columns)
        io = ScriptedIO(f"{row:0{n}b}")
        machine = _Machine([prefix + "n;"], io)
        while not machine.halted:
            machine.step()
        assert io.getvalue() == str(row // columns)
        assert machine.stack == [row % columns]
