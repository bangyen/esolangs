"""Each ledger row's proof scheme has a consequence you can measure."""

from __future__ import annotations

import pytest

import esolangs.languages.generators as boolean
from esolangs.generation.helpers import runs
from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import Ledger, Row, load
from tests.proofs._schemes import folds_without_tree
from tests.support.source_support import source_units

#: Every table at ``n == 3`` that depends on exactly one input, both
#: polarities, all at ones-count 4 -- the same ones-count as parity, so the
#: comparison measures structure and not density.  Both split orders appear
#: because a generator branching last-input-first folds ``10101010`` where an
#: MSB-first one folds ``11110000``.
_ONE_DEPENDENCY = (
    "11110000",
    "00001111",
    "11001100",
    "00110011",
    "10101010",
    "01010101",
)

#: Parity: the one n == 3 table with no constant subtree above a single row,
#: so nothing about it can fold.
_PARITY = "01101001"

#: A route that shrinks a degenerate table by at least this much is branching
#: on the table.  The threshold is the existing shape discriminator's.
_FOLD = 0.05

#: Lookup routes can shrink degenerate tables without branching. Their
#: mechanisms are documented in the ledger's per-language exemption bullets.
#: Named rather than derived: these are the structural proxy's known blind
#: spots, recorded per language as the ``folds_without_tree`` marker in its
#: package's ``[schemes]`` section, and the equality below requires the
#: prose and this set to agree.
_FOLDS_WITHOUT_TREE = folds_without_tree()

_LOOKUP_SCHEMES = frozenset({"finite lookup", "parameterized lookup", "linear lookup"})


@pytest.fixture(scope="module")
def ledger() -> Ledger:
    """The parsed ledger, read once for the module."""
    return load()


def _generator(row: Row) -> object:
    """The callable behind a ledger row."""
    for key, lang in BY_BOOLEAN.items():
        if lang.name == row.generator:
            return getattr(boolean, key)
    raise AssertionError(f"{row.generator} is not in BY_BOOLEAN")


def _fold(fn: object) -> float:
    """How much the shortest one-dependency build saves against parity."""
    assert callable(fn)
    parity = source_units(fn(_PARITY))
    best = min(source_units(fn(table)) for table in _ONE_DEPENDENCY)
    return 1 - best / parity


def _parameterized_rows(ledger: Ledger) -> list[Row]:
    return [
        row
        for row in ledger.rows
        if any(label.startswith("parameterized") for label in row.labels)
    ]


def test_parameterized_rows_embed_each_input_exactly_once() -> None:
    """A ``parameterized`` row's proof rests on the per-input embedding."""
    rows = _parameterized_rows(load())
    assert rows, "the ledger lists no parameterized rows"
    from esolangs.registry import LANGUAGES, recover_setters, template_char

    for row in rows:
        # The generator spells its inputs as runs of its declared character;
        # are read against the language's own setters, which refuse a stray
        # run, so three spans is exactly one per input.
        program = str(_generator(row)(_PARITY))
        assert "{X" not in program, row.generator
        language = LANGUAGES[row.generator].id
        char = template_char(language)
        assert char is not None
        spans = runs(program, char, recover_setters(language, program))
        assert len(spans) == 3, (
            f"{row.generator} is a {' '.join(row.labels)} row but embeds "
            f"{len(spans)} inputs at n=3 -- the scheme's argument needs "
            f"exactly one embedding per input"
        )


@pytest.mark.medium
def test_rows_without_a_tree_route_are_the_ones_the_ledger_names(
    ledger: Ledger,
) -> None:
    """Size dispatch names which lookup rows ship no tree route; check it."""
    measured_without = {
        row.generator
        for row in ledger.rows
        if set(row.labels) & _LOOKUP_SCHEMES and _fold(_generator(row)) < _FOLD
    }
    documented = set(ledger.no_tree_route)
    assert measured_without | _FOLDS_WITHOUT_TREE == documented, (
        f"lookup rows measuring no tree route: {sorted(measured_without)}; "
        f"the ledger documents: {sorted(documented)}"
    )


def test_the_documented_exemptions_are_real_ledger_rows(ledger: Ledger) -> None:
    """A name in the Size dispatch prose must be a generator, not a typo."""
    listed = {row.generator for row in ledger.rows}
    named = set(ledger.no_tree_route)
    assert named <= listed, f"not ledger rows: {sorted(named - listed)}"


def test_no_minterm_obligation_is_claimed(ledger: Ledger) -> None:
    """The `minterms` rows carry no measured obligation, and that is recorded."""
    rows = ledger.labelled("minterms")
    assert rows, "no ledger row is labelled minterms; retire this test"
    for row in rows:
        assert not set(row.labels) & _LOOKUP_SCHEMES, (
            f"{row.generator} is minterms and a lookup; a lookup row is measured"
        )
