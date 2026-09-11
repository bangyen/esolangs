"""Wrapping a generated program must not change what it computes.

``wrap_program``'s whole contract is that a break falls between two tokens,
so the program still means the same thing.  Every wrapper states that, and
each was checked against the shape its own language's programs have --
which is exactly the check that misses a token the pattern forgot.

Sophie's did.  Its pattern protected the ``#$48,`` print but not the bare
``$48`` a comparison comes with, nor the ``@$48{`` head, nor the ``}{``
between a conditional's two branches.  Nine of the 28 boundaries in an XOR
program were fatal, and the failure was silent: rows printed nothing or the
wrong digit, at every width below 13.  The committed example is wrapped to
80, where nothing splits, so nothing in the suite ran a narrow one.

This closes that by construction: generate at widths narrow enough to force
a break at almost every boundary, run the program, and compare against the
table it was built from.
"""

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
    """Return the languages whose programs a width actually reflows.

    A language with no wrapper is returned unchanged by ``wrap_program``, so
    there is nothing to break; the parameterized ones need their bits
    embedded, and the ones with an ``answer_convention`` need that prose
    decoded, so both are covered by their own suites instead.
    """
    return sorted(
        name
        for name, lang in LANGUAGES.items()
        if lang.boolean is not None
        and lang.id in WRAPPERS
        and not esolangs.describe(name)["parameterized"]
        and not esolangs.describe(name)["answer_convention"]
    )


def _evaluate(name: str, program: str, table: str) -> str:
    """Return the program's answer on every row of ``table``."""
    zero, one = esolangs.describe(name)["input_encoding"]  # type: ignore[misc]
    inputs = len(table).bit_length() - 1
    got = ""
    for row in range(len(table)):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        stdin = "".join(f"{one if bit else zero}\n" for bit in bits)
        got += esolangs.run(name, program, stdin=stdin, timeout=30)[-1:] or "?"
    return got


@pytest.mark.slow
@pytest.mark.parametrize("name", _wrappable())
def test_a_wrapped_program_computes_what_the_unwrapped_one_does(name: str) -> None:
    """At every width, the program still computes its table."""
    for table in _TABLES:
        reference = _evaluate(name, esolangs.generate(name, table), table)
        for width in _WIDTHS:
            wrapped = esolangs.generate(name, table, width=width)
            assert _evaluate(name, wrapped, table) == reference, (
                f"{name} at width {width} stops computing {table}: wrapping "
                f"broke a token its pattern does not name"
            )


@pytest.mark.slow
@pytest.mark.parametrize("width", _WIDTHS)
def test_sophie_survives_the_widths_that_used_to_break_it(width: int) -> None:
    """The regression itself, kept separate so it names the language."""
    assert _evaluate("Sophie", esolangs.generate("Sophie", "0110", width), "0110") == (
        "0110"
    )
