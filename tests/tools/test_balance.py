"""Balanced layouts retain program semantics and template setters."""

import random

import pytest

import esolangs
from esolangs.exceptions import ArgumentError
from esolangs.tools.befunge import balance_befunge, befunge
from esolangs.tools.super_snusp import (
    _super_snusp_layout,
    balance_super_snusp,
    super_snusp,
)
from esolangs.tools.wrap import balance_program, balance_score, wrap_program
from tests.test_cli import call_main


@pytest.mark.parametrize(
    "name",
    [
        "Brainfuck",
        "BIO",
        "Fractran",
        "Sbleq",
        "Slow ACV Mammalian",
        "Minifuck",
        "RAM0",
        "Bitdeque",
        "Befunge",
        "Fish",
        "Super_SNUSP",
        "Intercal",
        "EGL",
        "LaserFuck",
    ],
)
@pytest.mark.parametrize("table", ["0110", "0001", "10010110"])
def test_balance_executes(name: str, table: str) -> None:
    default = esolangs.generate(name, table)
    program = esolangs.generate(name, table, balance=True)
    assert isinstance(default, str)
    assert isinstance(program, str)
    assert balance_score(program) <= balance_score(default)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        if esolangs.describe(name)["parameterized"]:
            source, stdin = esolangs.instantiate(name, program, bits), ""
        else:
            source, stdin = program, esolangs.encode_inputs(name, bits)
        assert (
            esolangs.read_answer(name, esolangs.run(name, source, stdin, 10))
            == expected
        )


def test_balance_rejects_width() -> None:
    with pytest.raises(ArgumentError, match="mutually exclusive"):
        esolangs.generate("Brainfuck", "0110", 80, balance=True)


def test_character_balance() -> None:
    assert balance_program("+" * 100, "brainfuck") == "\n".join(["+" * 10] * 10)


def test_cli_balance(capsys: pytest.CaptureFixture[str]) -> None:
    output = call_main(["generate", "--balance", "Brainfuck", "0110"], capsys)
    assert output.rstrip("\n") == esolangs.generate("Brainfuck", "0110", balance=True)
    with pytest.raises(SystemExit):
        call_main(["generate", "--balance", "--width", "Brainfuck", "0110"], capsys)


def test_balance_raster_retains_layout() -> None:
    default = esolangs.generate("Piet", "0110")
    balanced = esolangs.generate("Piet", "0110", balance=True)
    assert isinstance(default, esolangs.Raster)
    assert isinstance(balanced, esolangs.Raster)
    assert balanced.to_png() == default.to_png()


@pytest.mark.parametrize("language", ["fractran", "sbleq", "slow_acv_mammalian"])
@pytest.mark.parametrize("cell", [1, 4, 7])
def test_equal_cells_reach_the_global_minimum(language: str, cell: int) -> None:
    for count in range(1, 33):
        program = " ".join(["1" * cell] * count)
        balanced = balance_program(program, language)
        if language == "slow_acv_mammalian" and cell != 4:
            continue
        optimum = min(
            (
                wrap_program(program, language, width)
                for width in range(1, len(program) + 1)
            ),
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)


@pytest.mark.parametrize("program", ["", "1 22 333 4444"])
def test_nonuniform_cells_retain_tokens(program: str) -> None:
    balanced = balance_program(program, "fractran")
    assert balanced.split() == program.split()
    assert balance_score(balanced) <= balance_score(program)


@pytest.mark.parametrize("language", ["fractran", "sbleq", "slow_acv_mammalian"])
@pytest.mark.parametrize("lengths", [(1, 1, 3), (2, 7, 1, 3), (1, 5, 2, 4, 1)])
def test_dominant_token_reaches_global_minimum(
    language: str, lengths: tuple[int, ...]
) -> None:
    program = " ".join("1" * length for length in lengths)
    balanced = balance_program(program, language)
    optimum = min(
        (
            wrap_program(program, language, width)
            for width in range(1, len(program) + 1)
        ),
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    assert balanced.split() == program.split()


def _super_snusp_tables() -> list[str]:
    tables = [
        f"{value:0{1 << inputs}b}"
        for inputs in range(1, 4)
        for value in range(1 << (1 << inputs))
    ]
    rng = random.Random(941)
    tables.extend(
        "".join(rng.choice("01") for _ in range(1 << inputs))
        for inputs in range(4, 7)
        for _ in range(8)
    )
    return tables


@pytest.mark.parametrize("table", _super_snusp_tables())
def test_super_snusp_balancing_reaches_global_minimum(table: str) -> None:
    flat = super_snusp(table)
    balanced = balance_super_snusp(flat)
    optimum = min(
        (_super_snusp_layout(flat, width) for width in range(1, len(flat) + 1)),
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    test_balance_executes("Super_SNUSP", table)


def test_super_snusp_balance_rejects_long_literals() -> None:
    with pytest.raises(ValueError, match="at most two cells"):
        balance_super_snusp("123.")


def _befunge_tables() -> list[str]:
    tables = [
        f"{value:0{1 << inputs}b}"
        for inputs in range(1, 4)
        for value in range(1 << (1 << inputs))
    ]
    rng = random.Random(952)
    for inputs in range(4, 11):
        tables.extend(
            "".join(rng.choice("01") for _ in range(1 << inputs)) for _ in range(4)
        )
        tables.extend(
            "".join(str((row.bit_count() + bias) % 2) for row in range(1 << inputs))
            for bias in (0, 1)
        )
    return tables


@pytest.mark.parametrize("table", _befunge_tables())
def test_befunge_balancing_reaches_global_minimum(table: str) -> None:
    default = befunge(table)
    balanced = balance_befunge(table, default)
    optimum = min(
        [default] + [befunge(table, width) for width in range(1, 81)],
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    rows = balanced.split("\n")
    assert len(rows) <= 25
    assert max(map(len, rows)) <= 80
    test_balance_executes("Befunge", table)


def test_befunge_balance_rejects_oversized_table() -> None:
    with pytest.raises(ValueError, match="at most ten inputs"):
        balance_befunge("0" * 2048, "")
