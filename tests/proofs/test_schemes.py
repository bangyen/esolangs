"""Each ledger row's proof scheme has a consequence you can measure.

``test_ledger.py`` checks the document against itself and the registry.  This
file checks it against the *generators*: a row claiming a scheme is claiming
its construction has that scheme's signature, and a signature is executable.

Two cautions, both learned by getting them wrong first.

The fold discriminator is a statement about the route *below* the crossover.
Sixteen of the twenty lookup rows fold a one-dependency table at ``n == 3``,
which looks like a contradiction until you notice ``n == 3`` sits under every
crossover -- those rows are measuring the tree route while the ledger names
the wide one.  Folding therefore cannot be turned into "folds implies `tree`".

Nor does the converse hold.  A tree may be *deliberately* unfolded: B-tapemark
and Container's sub-crossover route both keep uniform depth because their
nodes read the input, and collapsing a constant subtree would drop that
subtree's reads.  A 0% fold is those constructions working.  The obligations
below are the ones that survive both cautions.
"""

from __future__ import annotations

import pytest

import esolangs.tools as boolean
from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import Ledger, Row, load

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

#: Lookup rows whose sub-crossover route is a tree that deliberately does not
#: fold, so they measure 0% without lacking a tree route.  Container's nodes
#: read the input; collapsing a constant subtree would drop those reads and
#: break the read-count contract.  Kept separate from the ledger's own
#: exemption list because the reason is different: these *have* a tree.
_UNFOLDED_TREE_ROUTE = frozenset({"Container"})

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
    parity = len(str(fn(_PARITY)))
    best = min(len(str(fn(table))) for table in _ONE_DEPENDENCY)
    return 1 - best / parity


def _parameterized_rows(ledger: Ledger) -> list[Row]:
    return [
        row
        for row in ledger.rows
        if any(label.startswith("parameterized") for label in row.labels)
    ]


def test_parameterized_rows_embed_each_input_exactly_once() -> None:
    """A ``parameterized`` row's proof rests on the ``{Xi}`` embedding.

    Both parameterized schemes say the language "receives each bit through an
    equal-width ``{Xi}`` replacement" and embeds it *once* -- re-embedding an
    input at several decision nodes would make program length depend on the
    input, which is the hypothesis the equal-width argument needs.  So the
    placeholder count is the scheme's signature, and it is directly countable.

    Driving this from the ledger rather than from
    ``esolangs.tools.parameterized.__all__`` is deliberate.  Home Row is a
    parameterized generator -- its docstring says so and it emits ``{X0}`` --
    but it is absent from that module's roster, so the suite's existing
    exactly-once sweep has never run on it.  The ledger knows it is
    ``parameterized tree``, so reading the obligation from the ledger closes
    that hole without depending on the roster being complete.
    """
    rows = _parameterized_rows(load())
    assert rows, "the ledger lists no parameterized rows"
    from esolangs.registry import canonical_id, recover_setters
    from esolangs.tools.helpers import runs

    for row in rows:
        program = str(_generator(row)(_PARITY))
        if "{X" not in program:
            # A migrated generator spells its inputs as runs of ``$``; the
            # runs are read against the language's own setters, which
            # refuse a stray run, so three spans is exactly one per input.
            language = canonical_id(row.generator)
            spans = runs(program, "$", recover_setters(language, program))
            assert len(spans) == 3, (
                f"{row.generator} is a {' '.join(row.labels)} row but embeds "
                f"{len(spans)} inputs at n=3"
            )
            continue
        for i in range(3):
            placeholder = "{X" + str(i) + "}"
            assert program.count(placeholder) == 1, (
                f"{row.generator} is a {' '.join(row.labels)} row but emits "
                f"{placeholder} {program.count(placeholder)} times at n=3 -- "
                f"the scheme's argument needs exactly one embedding per input"
            )


def test_rows_without_a_tree_route_are_the_ones_the_ledger_names(
    ledger: Ledger,
) -> None:
    """Size dispatch names which lookup rows ship no tree route; check it.

    The paragraph claims *most* lookup rows carry a folded tree below a
    crossover and names the exceptions.  Measuring the fold at ``n == 3``
    tells you which rows actually have one, so the named list is falsifiable:
    a row that stops shipping its tree, or a newly linearized generator whose
    tree was dropped without the prose being revisited, moves out of the
    measured set and fails here.
    """
    measured_without = {
        row.generator
        for row in ledger.rows
        if set(row.labels) & _LOOKUP_SCHEMES and _fold(_generator(row)) < _FOLD
    }
    documented = set(ledger.no_tree_route) | _UNFOLDED_TREE_ROUTE
    assert measured_without == documented, (
        f"lookup rows measuring no tree route: {sorted(measured_without)}; "
        f"the ledger documents: {sorted(documented)}"
    )


def test_the_documented_exemptions_are_real_ledger_rows(ledger: Ledger) -> None:
    """A name in the Size dispatch prose must be a generator, not a typo."""
    listed = {row.generator for row in ledger.rows}
    named = set(ledger.no_tree_route) | _UNFOLDED_TREE_ROUTE
    assert named <= listed, f"not ledger rows: {sorted(named - listed)}"


def test_no_minterm_obligation_is_claimed(ledger: Ledger) -> None:
    """The `minterms` rows carry no measured obligation, and that is recorded.

    Three formulations were tried and all three are unfalsifiable or fitted.
    "Cannot fold" is false: two of the three rows shrink a one-dependency
    table sharply, because dependency reduction emits the smaller table a
    degenerate one really is.  "Size is flat at fixed ones-count" needs a
    threshold that admits 26.4% variation to pass Vandevelo, which is a
    number chosen to fit the rows rather than derived from the scheme.  "Size
    grows with ones-count" is false because complements handle the opposite
    polarity, so a 7-of-8 table costs what a 1-of-8 one does.

    What remains true is only the coverage claim, which is what the ledger
    actually asserts and what the arity sweeps already exercise.  This test
    pins the *absence* so the gap stays visible: if someone derives a real
    minterm signature later, it belongs here and this goes.
    """
    assert len(ledger.labelled("minterms")) == 3
