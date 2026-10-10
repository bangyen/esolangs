"""Every embedding generator holds the embed conventions."""

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
    """The stretches on which two equal-length programs differ, as a pair."""
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
    """Single embed, constant width and slot order are the template's shape."""
    import esolangs

    for name in _embedding():
        for n in _ARITIES:
            for table in _tables(n):
                template = esolangs.generate(name, table)
                assert template.inputs == n
                assert all(len(zero) == len(one) for zero, one in template.setters)


@pytest.mark.slow  # builds and fills every embedding generator at n=2, 3 and 5
def test_every_embedding_generator_holds_both_conventions() -> None:
    """No open cell is left: both measured conventions hold everywhere."""
    for name, example in _embedding().items():
        measured = _measure(example)
        failing = [column for column, ok in measured.items() if not ok]
        assert not failing, f"{name} fails {failing}"
