"""Balanced generator output and width selection."""

import pytest

import esolangs
from esolangs.exceptions import ArgumentError
from esolangs.generation.wrap import (
    balance_program,
    balance_score,
    wrap_chars,
    wrap_grid,
    wrap_program,
    wrap_space_delimited,
)
from esolangs.registry import LANGUAGES, SourceKind
from tests.support.cli_support import call_main
from tests.support.execution import run_observed
from tests.support.pick import first
from tests.support.reference import REFERENCE
from tests.support.witness_tables import row_bits

_TEXT = [
    lang
    for lang in LANGUAGES.values()
    if lang.backend is not None
    and lang.runtime.source_kind is SourceKind.TEXT
    and esolangs.describe(lang.name).answer_mode == "output"
]
# One of each route: the shared character balancer, a grid wrapper with no
# balancer, a language's own balancer, and a template filled per row.
BALANCED = sorted(
    {
        REFERENCE,
        next(
            lang.name
            for lang in _TEXT
            if lang.backend.balance is None
            and lang.backend.wrap is not None
            and lang.backend.wrap is not wrap_chars
        ),
        next(
            lang.name
            for lang in _TEXT
            if lang.backend.balance is not None
            and lang.backend.balance.__name__ != "_balance"
        ),
        first(
            parameterized=True,
            boolean_generator=True,
            answer_mode="output",
            self_halts=True,
        ),
    }
)
#: One language per token wrapper the global minimum is checked against.
CELLED = list(
    {
        lang.backend.wrap: lang.id
        for lang in LANGUAGES.values()
        if lang.backend is not None
        and lang.backend.wrap in (wrap_space_delimited, wrap_grid)
    }.values()
)


@pytest.mark.parametrize("name", BALANCED)
@pytest.mark.parametrize("table", ["0110", "10010110"])
def test_balance_executes(name: str, table: str) -> None:
    default = esolangs.generate(name, table)
    program = esolangs.generate(name, table, balance=True)
    assert isinstance(default.source, str)
    assert isinstance(program.source, str)
    assert balance_score(program.source) <= balance_score(default.source)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = row_bits(row, inputs)
        if esolangs.describe(name).parameterized:
            source, stdin = esolangs.instantiate(name, program, bits), ""
        else:
            source, stdin = program, esolangs.encode_inputs(name, bits)
        assert (
            esolangs.read_answer(
                name, run_observed(name, source, stdin=stdin, timeout=10).output
            )
            == expected
        )


def test_balance_rejects_width() -> None:
    with pytest.raises(ArgumentError, match="mutually exclusive"):
        esolangs.generate("Brainfuck", "0110", width=80, balance=True)


def test_character_balance() -> None:
    # 15 columns x 7 rows: |15 - 2*7| = 1; no width reaches 0.
    assert balance_program("+" * 100, REFERENCE) == "\n".join(
        ["+" * 15] * 6 + ["+" * 10]
    )


def test_cli_balance(capsys: pytest.CaptureFixture[str]) -> None:
    output = call_main(["generate", "--balance", "Brainfuck", "0110"], capsys)
    assert (
        output.rstrip("\n")
        == esolangs.generate("Brainfuck", "0110", balance=True).source
    )
    with pytest.raises(SystemExit):
        call_main(["generate", "--balance", "--width", "Brainfuck", "0110"], capsys)


@pytest.mark.parametrize("language", CELLED)
@pytest.mark.parametrize("cell", [1, 4, 7])
def test_equal_cells_reach_the_global_minimum(language: str, cell: int) -> None:
    for count in range(1, 33):
        program = " ".join(["1" * cell] * count)
        balanced = balance_program(program, language)
        optimum = min(
            (
                wrap_program(program, language, width)
                for width in range(1, len(program) + 1)
            ),
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)
