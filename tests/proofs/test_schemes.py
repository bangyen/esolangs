"""Each ledger row's proof scheme has a consequence you can measure."""

from __future__ import annotations

import pytest

import esolangs.tools as boolean
from esolangs.registry import BY_BOOLEAN
from esolangs.tools.helpers import runs
from tests.proofs._ledger import Ledger, Row, load
from tests.source_support import source_units

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

#: Lookup rows with no tree route that the fold discriminator cannot see:
#: their *lookup* route is what shrinks a degenerate table, so they fold like a
#: tree would.  Eval is one linear lookup at every arity, NoComment switches
#: between two lookups at four inputs, Suffolk's sweep shortens with every
#: input ``essential_inputs`` drops, and Collatz Multiverse spends a constant
#: and a decoder group on each distinct nibble its table holds,
#: bit~ indexes the projected table it is handed, Circlefuck tabulates its
#: essential inputs alone, Dimensional paints only as far as its last one, so
#: a table whose tail is constant zero is cheaper (6.9% on the best
#: one-dependency table) with no subtree involved, A Painter Ant's corridor
#: stops where the trailing run of equal answers starts (36.4%), and Unsquare
#: pushes only the cells the essential inputs address.  Cyclic tag, Bitwise
#: Cyclic Tag, ///, A Painter Ant, Forbin and Minsky Swap weight only the
#: essential inputs (``input_weights``): an ignored one costs an empty rule, a
#: bare ``0``, an ``X``-deleted bit, a bare ``SN``, a read into the scratch
#: name or a drained ``~ ~``; Fish reads and pops it (``i~``), Packlang reads
#: it bare, Flowchart skips its eight bits and Clockwise reads its seven
#: before the next input's overwrite them; BIO parks its index while an
#: ignored setter runs.  Named rather
#: than derived because the proxy is structural and these are its known blind
#: spot; a further such row has to be added here, which is the point -- the
#: equality below then fails until the prose and this set agree.
_FOLDS_WITHOUT_TREE = frozenset(
    {
        "///",
        "A Painter Ant",
        "BIO",
        "Bitwise Cyclic Tag",
        "bit~",
        "Circlefuck",
        "Clockwise",
        "Collatz Multiverse",
        "Cyclic tag",
        "Dimensional",
        "Eval",
        "Fish",
        "Flowchart",
        "Forbin",
        "Minsky Swap",
        "NoComment",
        "Packlang",
        "Suffolk",
        "Unsquare",
    }
)

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
    from esolangs.registry import canonical_id, recover_setters, template_char

    for row in rows:
        # The generator spells its inputs as runs of its declared character;
        # are read against the language's own setters, which refuse a stray
        # run, so three spans is exactly one per input.
        program = str(_generator(row)(_PARITY))
        assert "{X" not in program, row.generator
        language = canonical_id(row.generator)
        char = template_char(language)
        assert char is not None
        spans = runs(program, char, recover_setters(language, program))
        assert len(spans) == 3, (
            f"{row.generator} is a {' '.join(row.labels)} row but embeds "
            f"{len(spans)} inputs at n=3 -- the scheme's argument needs "
            f"exactly one embedding per input"
        )


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
    assert len(ledger.labelled("minterms")) == 3
