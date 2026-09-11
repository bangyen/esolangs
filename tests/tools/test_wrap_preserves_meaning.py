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
    """Return every language whose programs a width actually reflows.

    A language with no wrapper is returned unchanged by ``wrap_program``, so
    there is nothing to break.  Everything else is in, **including the
    parameterized ones**: excluding them is what let Minifuck and Bitdeque
    through.  Their templates are not wrapped, but the program
    :func:`~esolangs.instantiate` builds from one is, and both were silently
    computing the wrong table at several widths -- Minifuck because a
    newline landed where a collapsed ``[`` skips, Bitdeque because one
    between ``GOTO`` and its operand deleted both from the token stream.

    The three answer-by-terminating languages stay out: a wrong answer there
    is an infinite loop, not a wrong character, so this harness cannot read
    a verdict from them at all.
    """
    return sorted(
        name
        for name, lang in LANGUAGES.items()
        if lang.boolean is not None
        and lang.id in WRAPPERS
        and esolangs.describe(name)["answer_mode"] != "termination"
    )


def _evaluate(name: str, table: str, width: int | None) -> str:
    """Return the program's answer on every row of ``table``, at ``width``.

    A template is built by :func:`~esolangs.instantiate`, which is where a
    parameterized language's width is applied; everything else takes the
    width from :func:`~esolangs.generate`.  The answer is the last
    non-whitespace character either way -- for the state-dumping languages
    that is the cell the generator writes into, which their
    ``answer_convention`` names.
    """
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
    """At every width, the program still computes its table."""
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
    """The regression itself, kept separate so it names the language."""
    assert _evaluate("Sophie", "0110", width) == "0110"
