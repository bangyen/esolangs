import pytest

import esolangs
from esolangs.exceptions import ArgumentError
from esolangs.registry import LANGUAGES, SourceKind
from esolangs.tools.helpers import mark
from esolangs.tools.wrap import (
    _mammalian,
    balance_program,
    balance_score,
    wrap_grid,
    wrap_program,
    wrap_space_delimited,
)
from tests.cli.test_cli import call_main
from tests.reference import REFERENCE
from tests.support.pick import first
from tests.support.witness_tables import row_bits

_TEXT = [
    lang
    for lang in LANGUAGES.values()
    if lang.boolean
    and lang.source_kind is SourceKind.TEXT
    and esolangs.describe(lang.name)["answer_mode"] == "output"
]
# One of each route: the shared character balancer, a grid wrapper with no
# balancer, a language's own balancer, and a template filled per row.
BALANCED = sorted(
    {
        REFERENCE,
        next(
            lang.name
            for lang in _TEXT
            if lang.balance is None
            and lang.wrap is not None
            and lang.wrap.__name__ != "wrap_chars"
        ),
        next(
            lang.name
            for lang in _TEXT
            if lang.balance is not None and lang.balance.__name__ != "_balance"
        ),
        first(
            parameterized=True,
            boolean_generator=True,
            answer_mode="output",
            self_halts=True,
        ),
    }
)
_MAMMAL = next(
    (lang.id for lang in LANGUAGES.values() if lang.wrap is _mammalian), None
)
#: One language per token wrapper the global minimum is checked against.
CELLED = list(
    {
        lang.wrap: lang.id
        for lang in LANGUAGES.values()
        if lang.wrap in (wrap_space_delimited, wrap_grid, _mammalian)
    }.values()
)


@pytest.mark.parametrize("name", BALANCED)
@pytest.mark.parametrize("table", ["0110", "10010110"])
def test_balance_executes(name: str, table: str) -> None:
    default = esolangs.generate(name, table)
    program = esolangs.generate(name, table, balance=True)
    assert isinstance(default, str)
    assert isinstance(program, str)
    assert balance_score(program) <= balance_score(default)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = row_bits(row, inputs)
        if esolangs.describe(name)["parameterized"]:
            source, stdin = esolangs.instantiate(name, program, bits), ""
        else:
            source, stdin = program, esolangs.encode_inputs(name, bits)
        assert (
            esolangs.read_answer(
                name, esolangs.run(name, source, stdin=stdin, timeout=10)
            )
            == expected
        )


def test_balance_rejects_width() -> None:
    with pytest.raises(ArgumentError, match="mutually exclusive"):
        esolangs.generate("Brainfuck", "0110", width=80, balance=True)


def test_character_balance() -> None:
    assert balance_program("+" * 100, REFERENCE) == "\n".join(["+" * 10] * 10)
    marker = mark(0) * 100
    assert balance_program(marker + "+" * 100, REFERENCE) == marker + "\n" + "\n".join(
        "+" * 100
    )


def test_cli_balance(capsys: pytest.CaptureFixture[str]) -> None:
    output = call_main(["generate", "--balance", "Brainfuck", "0110"], capsys)
    assert output.rstrip("\n") == esolangs.generate("Brainfuck", "0110", balance=True)
    with pytest.raises(SystemExit):
        call_main(["generate", "--balance", "--width", "Brainfuck", "0110"], capsys)


@pytest.mark.parametrize("language", CELLED)
@pytest.mark.parametrize("cell", [1, 4, 7])
def test_equal_cells_reach_the_global_minimum(language: str, cell: int) -> None:
    for count in range(1, 33):
        program = " ".join(["1" * cell] * count)
        balanced = balance_program(program, language)
        if language == _MAMMAL and cell != 4:
            continue
        optimum = min(
            (
                wrap_program(program, language, width)
                for width in range(1, len(program) + 1)
            ),
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)
