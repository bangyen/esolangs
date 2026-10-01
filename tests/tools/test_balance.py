"""Balanced layouts retain program semantics and template setters."""

import pytest

import esolangs
from esolangs.exceptions import ArgumentError
from esolangs.tools.wrap import balance_program, balance_score
from tests.test_cli import call_main


@pytest.mark.parametrize(
    "name",
    [
        "Brainfuck",
        "BIO",
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
