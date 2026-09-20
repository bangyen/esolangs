"""``docs/roadmap.md``'s scaling audit must agree with the registry and the suite.

The measured half of the scaling contract lives in
``tests/proofs/deep/linearity.py``: it builds every generator at rising arity
and costs around thirty seconds, so it runs from ``just proofs`` rather than
from pytest.  This file is the cheap half.  Parsing a table and comparing name
sets runs no generator, so it stays in the fast band and gates every push.

What it is for: the audit's contents are duplicated in
``tests/tools/test_boolean_contract.py`` as three hand-maintained sets, and a
duplicated list is free to drift.  That is not hypothetical here -- the same
file's ``_DOCUMENTED_SIZES`` kept COD at 942,692 characters for n=8 through the
commit that linearized it down to 294, and nothing failed, because the test
holding it carries the ``slow`` marker and PR CI does not run it.
"""

from __future__ import annotations

import pytest

from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import UNSETTLED_SCALING
from tests.proofs._ledger import load as load_ledger
from tests.proofs._roadmap import SETTLED, TOTAL, Audit, load
from tests.proofs.deep.execution import EXEMPT as _EXECUTION_EXEMPT
from tests.proofs.deep.execution import exempt_generators as execution_exempt
from tests.proofs.deep.linearity import exempt_generators
from tests.tools.test_boolean_contract import (
    _LANGUAGE_SUPERLINEAR_SCALING,
    _LINEAR_SCALING,
    _OPEN_SCALING,
)

#: Every verdict the audit's three scaling columns are allowed to carry.
#: Listed so a typo cannot quietly reclassify a row: anything unrecognized
#: reads as "not settled", which would silently *exempt* a generator from the
#: bound.  The totality column carries the ledger's own labels instead.
_VERDICTS = SETTLED | {"Open", "Language lower bound"}
_TOTALITY_VERDICTS = {TOTAL, "Cap", "Exception"}


@pytest.fixture(scope="module")
def audit() -> Audit:
    """The parsed scaling audit, read once for the module."""
    return load()


def _display(keys: set[str]) -> set[str]:
    """Registry keys as the display names the documents use."""
    return {BY_BOOLEAN[key].name for key in keys}


def test_the_audit_names_real_generators(audit: Audit) -> None:
    """Every row names a generator the registry actually has."""
    names = {lang.name for lang in BY_BOOLEAN.values()}
    assert {row.generator for row in audit.rows} <= names


def test_every_audit_verdict_is_a_known_one(audit: Audit) -> None:
    """An unrecognized verdict would silently exempt a row from the bound."""
    for row in audit.rows:
        assert row.totality in _TOTALITY_VERDICTS, row
        assert row.generation_time in _VERDICTS, row
        assert row.output_size in _VERDICTS, row
        assert row.execution_time in _VERDICTS, row


def test_the_audit_holds_only_unresolved_rows(audit: Audit) -> None:
    """Rows leave the table when they close, so every row left is open.

    This is what lets the contract treat "absent from the table" as "held to
    the bound" rather than needing a second list of closed generators.  Open
    means open on *some* axis; the size contract's own exemption set is the
    narrower ``unsettled``.
    """
    assert all(row.is_open for row in audit.rows)
    assert audit.unsettled <= {row.generator for row in audit.rows}


def test_the_totality_column_is_the_ledger(audit: Audit) -> None:
    """A ``Cap`` or ``Exception`` cell is ``proofs.md``'s label, spelled twice.

    Every ledger row carrying one of those labels must appear here with the
    same verdict, and no row here may claim one the ledger does not.
    """
    ledger = {
        row.generator: next(lab for lab in ("cap", "exception") if lab in row.labels)
        for row in load_ledger().rows
        if "cap" in row.labels or "exception" in row.labels
    }
    audited = {
        row.generator: row.totality.lower()
        for row in audit.rows
        if row.totality != TOTAL
    }
    assert audited == ledger


def test_the_suites_hand_kept_sets_match_the_audit(audit: Audit) -> None:
    """The contract suite's scaling sets are the audit, spelled twice.

    ``_OPEN_SCALING`` and ``_LANGUAGE_SUPERLINEAR_SCALING`` together are the
    audit's rows; ``_LINEAR_SCALING`` is disjoint from them.  Whichever copy is
    edited, the other has to follow.
    """
    unresolved = _display(_OPEN_SCALING | _LANGUAGE_SUPERLINEAR_SCALING)
    assert unresolved == audit.unsettled
    assert _display(_LINEAR_SCALING) & audit.unsettled == set()


def test_the_scaling_column_is_the_audit(audit: Audit) -> None:
    """A ledger row is ``open``, ``lower bound`` or ``measured`` iff it is audited.

    The proofs ledger's Scaling column and the roadmap's audit table state
    the same thing twice: a row whose generation time or output size is not
    settled in the audit carries one of those classes, and no other row
    does.  ``lower bound`` is the audit's ``Language lower bound`` cell.
    """
    ledger = load_ledger()
    unsettled = {
        row.generator for row in ledger.rows if row.scaling_class in UNSETTLED_SCALING
    }
    audited = {
        row.generator
        for row in audit.rows
        if row.generation_time not in SETTLED or row.output_size not in SETTLED
    }
    assert unsettled == audited
    bounded = {
        row.generator for row in ledger.rows if row.scaling_class == "lower bound"
    }
    assert bounded == {
        row.generator
        for row in audit.rows
        if "Language lower bound" in (row.generation_time, row.output_size)
    }


def test_the_exempt_set_is_read_from_both_documents(audit: Audit) -> None:
    """The bound's exemptions come from the roadmap and from ``proofs.md``.

    Pinned here because the measured half is not collected by pytest: if the
    exemption source silently narrowed to one document, the only signal would
    be a generator quietly ceasing to be checked.
    """
    exempt = exempt_generators()
    ledger = load_ledger()
    qualified = {
        row.generator
        for row in ledger.rows
        if "cap" in row.labels or "exception" in row.labels
    }
    assert set(exempt) == audit.unsettled | qualified
    assert set(exempt) <= {lang.name for lang in BY_BOOLEAN.values()}
    # Every exemption carries a reason naming which document granted it.
    assert all(why for why in exempt.values())


def test_the_execution_exempt_set_is_read_from_both_documents(audit: Audit) -> None:
    """The command-count bound's exemptions come from the same two documents.

    Its own hand-kept set is the one generator that answers by never
    halting; everything else is a ``proofs.md`` cap row or an audit row
    whose execution cell is open, so a row closing there arms the band.
    """
    exempt = execution_exempt()
    ledger = load_ledger()
    qualified = {
        row.generator
        for row in ledger.rows
        if "cap" in row.labels or "exception" in row.labels
    }
    assert set(exempt) == set(_EXECUTION_EXEMPT) | audit.execution_unsettled | qualified
    assert audit.execution_unsettled <= {row.generator for row in audit.rows}
    assert all(why for why in exempt.values())


def test_the_contract_covers_generators_the_original_queue_missed() -> None:
    """The point of the registry-wide contract: it is wider than the queue.

    The roadmap's scaling item enumerated twenty-five languages, and the
    suite's existing linearity test covered exactly those.  Thirty-nine
    generators were never checked, which is why this exists.

    (ZTOALC L, Nopstacle and COD entered the same way and left with their
    languages.)  Growing this number is the contract doing its job, so the
    assertion is on the *original* twenty-five.
    """
    queue = _LINEAR_SCALING | _LANGUAGE_SUPERLINEAR_SCALING | _OPEN_SCALING
    assert len(queue) == 24
    assert len(BY_BOOLEAN) - len(queue) == 38
