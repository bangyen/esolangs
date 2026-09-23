"""Every embedding generator holds the embed conventions.

The measured half builds every embedding generator, fills every row, and reads
the two measured conventions -- no spaces, uniform -- off the programs; each
generator must hold both.  The other three -- single embed, constant width,
slot order -- are the template object's shape and are checked by its
constructor, which ``generate`` runs for every template; a test here pins that
they hold for every embedding generator at every arity measured.

Every convention is about the *embed*, the text a fill substitutes for one
input's run.  It is read off the programs rather than off the fill, since four
fills are not plain substitutions: for one input, the two fills that differ
only in that bit are compared and the span on which they differ is the
embed pair.  A blank in it is a delimiter when it stands alone between two
non-blank characters (Bitdeque's ``INVERT PUSH``) and content otherwise --
a bit spelled as a blank cell, or a blank pad.  The embed is *uniform* when
that pair is the same pair for every input of every table.
"""

from __future__ import annotations

import itertools
import re

import pytest

from esolangs.registry import BY_BOOLEAN
from esolangs.tools.examples import BOOLEAN_EXAMPLES, BooleanExample

#: The arities every convention is read at.  Five is in the list because it
#: is where Bitdeque switches to its linear route, which the suite's own
#: equal-width test (n=1..2) never reaches.
_ARITIES = (2, 3, 5)

#: A single blank between two non-blank characters: the delimiter shape.
_DELIMITER = re.compile(r"(?<=\S) (?=\S)")


def _embedding() -> dict[str, BooleanExample]:
    """The embedding examples, keyed by the registry display name."""
    names = {lang.interpreter: lang.name for lang in BY_BOOLEAN.values()}
    return {
        names[example.interpreter]: example
        for example in BOOLEAN_EXAMPLES.values()
        if example.fill is not None
    }


def _tables(n: int) -> tuple[str, str]:
    parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**n))
    dense = "".join("1" if (i * 7 + 3) % 5 < 2 else "0" for i in range(2**n))
    return parity, dense


def _span(a: str, b: str) -> tuple[str, str]:
    """The stretches on which two equal-length programs differ, as a pair.

    Taken row by row and joined with newlines, so a grid fill that writes
    one input's cells on two rows yields those
    cells and not the untouched rows between them.
    """
    zero, one = [], []
    for x, y in zip(a.split("\n"), b.split("\n"), strict=True):
        if x == y:
            continue
        if len(x) != len(y):  # a ragged grid moved a row's end: whole row
            zero.append(x)
            one.append(y)
            continue
        lo = next(i for i in range(len(x)) if x[i] != y[i])
        hi = next(i for i in range(len(x) - 1, -1, -1) if x[i] != y[i])
        zero.append(x[lo : hi + 1])
        one.append(y[lo : hi + 1])
    return "\n".join(zero), "\n".join(one)


def _content_blank(embed: str) -> bool:
    """Whether a blank in ``embed`` is more than a delimiter."""
    return " " in _DELIMITER.sub("", embed)


def _measure(example: BooleanExample) -> dict[str, bool]:
    """Whether each convention holds at every arity, both shapes, every fill."""
    assert example.fill is not None
    spaces = True
    pairs: set[tuple[str, str]] = set()
    for n in _ARITIES:
        for table in _tables(n):
            template = example.generator(table, **dict(example.kwargs))
            programs = {
                bits: example.fill(template, list(bits))
                for bits in itertools.product((0, 1), repeat=n)
            }
            assert len({len(p) for p in programs.values()}) == 1  # the constructor's
            for bits, program in programs.items():
                for i in range(n):
                    if bits[i]:
                        continue
                    other = programs[(*bits[:i], 1, *bits[i + 1 :])]
                    pair = _span(program, other)
                    pairs.add(pair)
                    spaces &= not any(map(_content_blank, pair))
    return {"No spaces": spaces, "Uniform": len(pairs) == 1}


def test_the_structural_conventions_hold_where_the_template_is_made() -> None:
    """Single embed, constant width and slot order are the template's shape.

    ``generate`` builds the template object for every embedding generator,
    and its constructor refuses a pair of unequal width or runs that do not
    fit the pairs; so building every template at every measured arity is
    the check, and the audit table has no column for these three.
    """
    import esolangs

    for name in _embedding():
        for n in _ARITIES:
            for table in _tables(n):
                template = esolangs.generate(name, table)
                assert template.inputs == n
                assert all(len(zero) == len(one) for zero, one in template.setters)


@pytest.mark.slow  # builds and fills every embedding generator at n=2, 3 and 5
def test_every_embedding_generator_holds_both_conventions() -> None:
    """No open cell is left: both measured conventions hold everywhere.

    The audit that tracked the open set closed, so this reads as one claim
    over the whole set rather than against a table; a regression is a
    generator that stops holding one.
    """
    for name, example in _embedding().items():
        measured = _measure(example)
        failing = [column for column, ok in measured.items() if not ok]
        assert not failing, f"{name} fails {failing}"


def test_bitdeque_linear_route_is_one_width() -> None:
    """The route the equal-width test misses stays at one length.

    Its ``EJECT ``/``POP `` units once left 32 lengths for 32 five-input
    rows; block pads closed that, and now the weight is the template's
    (the discard blocks) and every input is the one eleven-character
    pair, so the row has left the audit.  This pins the arity where the
    route begins.
    """
    example = _embedding()["Bitdeque"]
    assert example.fill is not None
    for n in (4, 5):
        template = example.generator(_tables(n)[0])
        lengths = {
            len(example.fill(template, list(bits)))
            for bits in itertools.product((0, 1), repeat=n)
        }
        assert len(lengths) == 1, (n, sorted(lengths))
