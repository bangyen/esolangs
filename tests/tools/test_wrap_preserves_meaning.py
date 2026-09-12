r"""Wrapping a generated program must not change what it computes."""

from __future__ import annotations

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import WRAPPERS

# Narrow enough to break.
# so the breaks land in.
_WIDTHS = (5, 11, 27)

_TABLES = ("0110", "0001")


def _wrappable() -> list[str]:
    r"""Return every language whose programs a width actually reflows."""
    return sorted(
        name
        for name, lang in LANGUAGES.items()
        if lang.boolean is not None
        and lang.id in WRAPPERS
        and esolangs.describe(name)["answer_mode"] != "termination"
    )


def _evaluate(name: str, table: str, width: int | None) -> str:
    r"""Return the program's answer on every row of ``table``, at ``width``."""
    parameterized = esolangs.describe(name)["parameterized"]
    program = esolangs.generate(name, table, None if parameterized else width)
    inputs = len(table).bit_length() - 1
    got = ""
    for row in range(len(table)):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        if parameterized:
            source, stdin = esolangs.instantiate(name, program, bits, width), ""
        else:
            source, stdin = program, esolangs.encode_inputs(name, bits)
        got += esolangs.run(name, source, stdin=stdin, timeout=30).strip()[-1:] or "?"
    return got


@pytest.mark.slow
@pytest.mark.parametrize("name", _wrappable())
def test_a_wrapped_program_computes_what_the_unwrapped_one_does(name: str) -> None:
    r"""At every width, the program still computes its table."""
    for table in _TABLES:
        reference = _evaluate(name, table, None)
        for width in _WIDTHS:
            assert _evaluate(name, table, width) == reference, (
                f"{name} at width {width} stops computing {table}: wrapping "
                f"broke a token its pattern does not name"
            )


@pytest.mark.slow
@pytest.mark.parametrize("width", _WIDTHS)
def test_sophie_survives_the_widths_that_used_to_break_it(width: int) -> None:
    r"""The regression itself, kept separate so it names the language."""
    assert _evaluate("Sophie", "0110", width) == "0110"


def _lays_itself_out() -> list[str]:
    r"""Return the languages that take a width in the generator."""
    return sorted(
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["width_aware"]
        and esolangs.describe(name)["answer_mode"] != "termination"
    )


@pytest.mark.slow
@pytest.mark.parametrize("name", _lays_itself_out())
def test_a_width_laid_out_program_computes_what_the_unbounded_one_does(
    name: str,
) -> None:
    r"""A generator that lays itself out must still emit a *valid* program."""
    for table in _TABLES:
        reference = _evaluate(name, table, None)
        for width in _WIDTHS:
            assert _evaluate(name, table, width) == reference, (
                f"{name} at width {width} stops computing {table}: its "
                f"layout does not survive the width it was given"
            )


@pytest.mark.slow
@pytest.mark.parametrize("width", [2, 5, 11, 20, 27, 35, 36, 60])
def test_streetcode_lays_out_every_two_input_table(width: int) -> None:
    r"""The regression itself, kept separate so it names the language."""
    for table in ("0001", "0010", "1101", "1110", "0110"):
        assert esolangs.evaluate("Streetcode", table, timeout=30, width=width) == table
