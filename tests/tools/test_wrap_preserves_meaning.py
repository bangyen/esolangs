"""Wrapping a generated program must not change what it computes."""

from __future__ import annotations

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import WRAPPERS

# Narrow enough to break somewhere in almost every program, and coprime-ish
# so the breaks land in different places rather than all at one stride.
_WIDTHS = (5, 11, 27)

_TABLES = ("0110", "0001")


def _wrappable() -> list[str]:
    """Return every language whose programs a width actually reflows."""
    return sorted(
        name
        for name, lang in LANGUAGES.items()
        if lang.boolean is not None
        and lang.id in WRAPPERS
        and esolangs.describe(name)["answer_mode"] != "termination"
    )


def _evaluate(name: str, table: str, width: int | None) -> str:
    """Return the program's answer on every row of ``table``, at ``width``."""
    parameterized = esolangs.describe(name)["parameterized"]
    program = esolangs.generate(name, table, width=None if parameterized else width)
    inputs = len(table).bit_length() - 1
    got = ""
    for row in range(len(table)):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        if parameterized:
            source, stdin = esolangs.instantiate(name, program, bits, width=width), ""
        else:
            source, stdin = program, esolangs.encode_inputs(name, bits)
        got += esolangs.run(name, source, stdin=stdin, timeout=30).strip()[-1:] or "?"
    return got


@pytest.mark.slow
@pytest.mark.parametrize("name", _wrappable())
def test_a_wrapped_program_computes_what_the_unwrapped_one_does(name: str) -> None:
    """At every width, the program still computes its table."""
    for table in _TABLES:
        reference = _evaluate(name, table, None)
        for width in _WIDTHS:
            assert _evaluate(name, table, width) == reference, (
                f"{name} at width {width} stops computing {table}: wrapping "
                f"broke a token its pattern does not name"
            )
