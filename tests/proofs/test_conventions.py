"""``docs/roadmap.md``'s conventions audit must agree with the generators.

The cheap half parses the table and checks its names and vocabulary.  The
measured half builds every embedding generator, fills every row, and reads
the four conventions off the programs: an absent generator must hold all
four, a ``Holds`` cell must hold, and an open cell must fail -- so a fix
that lands without its row leaving is caught as well as a regression.

Every convention is about the *embed*, the text a fill substitutes for one
``{Xi}``.  It is read off the programs rather than off the fill, since four
fills are not plain substitutions: for one input, the two fills that differ
only in that bit are compared and the span on which they differ is the
embed pair.  A blank in it is a delimiter when it stands alone between two
non-blank characters (Bitdeque's ``INVERT PUSH``) and content otherwise --
a bit spelled as a blank cell, or a blank pad.
"""

from __future__ import annotations

import itertools
import re

import pytest

from esolangs.registry import BY_BOOLEAN
from esolangs.tools.examples import BOOLEAN_EXAMPLES, BooleanExample
from tests.proofs._conventions import HOLDS, LANGUAGE, OPEN, Conventions, load

_VERDICTS = {HOLDS, OPEN, LANGUAGE}

#: The arities every convention is read at.  Five is in the list because it
#: is where Bitdeque switches to its linear route, which the suite's own
#: equal-width test (n=1..2) never reaches.
_ARITIES = (2, 3, 5)

#: A single blank between two non-blank characters: the delimiter shape.
_DELIMITER = re.compile(r"(?<=\S) (?=\S)")


@pytest.fixture(scope="module")
def audit() -> Conventions:
    """The parsed conventions audit, read once for the module."""
    return load()


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
    one input's cells on two rows (COD's swim and its return) yields those
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
    single = width = order = spaces = True
    for n in _ARITIES:
        for table in _tables(n):
            template = example.generator(table, **dict(example.kwargs))
            slots = [int(s) for s in re.findall(r"\{X(\d+)\}", template)]
            single &= sorted(slots) == list(range(n)) and "{C" not in template
            order &= slots == sorted(slots)
            programs = {
                bits: example.fill(template, list(bits))
                for bits in itertools.product((0, 1), repeat=n)
            }
            width &= len({len(p) for p in programs.values()}) == 1
            if not width:
                continue  # the spans below need equal lengths
            for bits, program in programs.items():
                for i in range(n):
                    if bits[i]:
                        continue
                    other = programs[(*bits[:i], 1, *bits[i + 1 :])]
                    spaces &= not any(map(_content_blank, _span(program, other)))
    return {
        "Single embed": single,
        "Constant width": width,
        "Slot order": order,
        "No spaces": spaces,
    }


def test_the_audit_names_real_embedding_generators(audit: Conventions) -> None:
    assert set(audit.by_name()) <= set(_embedding())


def test_every_verdict_is_a_known_one(audit: Conventions) -> None:
    for row in audit.rows:
        assert set(row.verdicts) <= _VERDICTS, row


def test_the_audit_holds_only_open_rows(audit: Conventions) -> None:
    closed = [row.generator for row in audit.rows if not row.is_open]
    assert not closed, f"rows that hold every convention should leave: {closed}"


@pytest.mark.slow  # builds and fills every embedding generator at n=2, 3 and 5
def test_the_audit_matches_the_programs(audit: Conventions) -> None:
    rows = audit.by_name()
    for name, example in _embedding().items():
        measured = _measure(example)
        row = rows.get(name)
        if row is None:
            failing = [c for c, ok in measured.items() if not ok]
            assert not failing, f"{name} is absent from the audit but fails {failing}"
            continue
        for column, verdict in zip(measured, row.verdicts, strict=True):
            if verdict == HOLDS:
                assert measured[column], f"{name}: {column} is {verdict} but fails"
            else:
                assert not measured[column], f"{name}: {column} is {verdict} but holds"


def test_the_language_cell_has_no_other_symbol(audit: Conventions) -> None:
    """Nopstacle's ``Language`` verdict: the alphabet is the blank and ``#``.

    A ``Language`` cell claims no command can spell the bit.  For Nopstacle
    that is the loader's own rule -- any character but those two is
    refused -- and the two fills of one bit differ only in blanks against
    ``#``, so there is nothing else to spell it with.
    """
    from esolangs.interpreters.grid_based.nopstacle import _Machine

    language = [row.generator for row in audit.rows if row.no_spaces == LANGUAGE]
    assert language == ["Nopstacle"]
    with pytest.raises(ValueError, match="spaces or '#'"):
        _Machine([" x"])
    example = _embedding()["Nopstacle"]
    assert example.fill is not None
    template = example.generator("0110")
    zero, one = _span(example.fill(template, [0, 0]), example.fill(template, [0, 1]))
    assert set(zero + one) <= {" ", "#", "\n"}
    assert " " in zero + one


def test_bitdeque_linear_route_is_one_width(audit: Conventions) -> None:
    """The route the equal-width test misses stays at one length.

    Its ``EJECT ``/``POP `` units once left 32 lengths for 32 five-input
    rows; the block pads in :func:`esolangs.tools.examples._fill_bitdeque`
    closed that, and this pins the arity where the route begins.
    """
    assert "Bitdeque" not in audit.by_name()
    example = _embedding()["Bitdeque"]
    assert example.fill is not None
    for n in (4, 5):
        template = example.generator(_tables(n)[0])
        lengths = {
            len(example.fill(template, list(bits)))
            for bits in itertools.product((0, 1), repeat=n)
        }
        assert len(lengths) == 1, (n, sorted(lengths))
