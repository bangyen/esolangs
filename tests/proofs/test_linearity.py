"""``docs/roadmap.md``'s scaling audit must agree with the registry and the suite."""

from __future__ import annotations

from dataclasses import fields

import pytest

from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import UNSETTLED_SCALING
from tests.proofs._ledger import load as load_ledger
from tests.proofs._roadmap import SETTLED, TOTAL, Audit, AuditRow, load
from tests.proofs.deep.execution import EXEMPT as _EXECUTION_EXEMPT
from tests.proofs.deep.execution import exempt_generators as execution_exempt
from tests.proofs.deep.linearity import exempt_generators

#: Every verdict the audit's three scaling columns are allowed to carry.
#: Listed so a typo cannot quietly reclassify a row: anything unrecognized
#: reads as "not settled", which would silently *exempt* a generator from the
#: bound.  The totality column carries the ledger's own labels instead.
_VERDICTS = SETTLED | {"Measured", "Open", "Language lower bound"}
_TOTALITY_VERDICTS = {TOTAL, "Cap", "Exception"}


@pytest.fixture(scope="module")
def audit() -> Audit:
    """The parsed scaling audit, read once for the module."""
    return load()


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


def test_the_audit_holds_only_unresolved_rows(audit: Audit) -> None:
    """Rows leave the table when they close, so every row left is open."""
    assert all(row.is_open for row in audit.rows)
    assert audit.unsettled <= {row.generator for row in audit.rows}


def test_every_audit_column_has_an_open_cell(audit: Audit) -> None:
    """Columns leave too: Execution time sat ``Linear`` on every row."""
    for axis in (f.name for f in fields(AuditRow) if f.name != "generator"):
        closed = {TOTAL} if axis == "totality" else SETTLED
        assert any(getattr(row, axis) not in closed for row in audit.rows), axis


def test_the_totality_column_is_the_ledger(audit: Audit) -> None:
    """A ``Cap`` or ``Exception`` cell is ``proofs/index.md``'s label, spelled twice."""
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


def test_the_scaling_column_is_the_audit(audit: Audit) -> None:
    """A ledger row is ``open``, ``lower bound`` or ``measured`` iff it is audited."""
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
    """The bound's exemptions come from the roadmap and from ``proofs/index.md``."""
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


def test_the_execution_exempt_set_is_the_unmeasured_column() -> None:
    """The command-count bound exempts exactly the ``unmeasured`` Execution cells."""
    exempt = execution_exempt()
    ledger = load_ledger()
    qualified = {
        row.generator
        for row in ledger.rows
        if "cap" in row.labels or "exception" in row.labels
    }
    unmeasured = {
        row.generator for row in ledger.rows if row.execution_class == "unmeasured"
    }
    assert set(exempt) == set(_EXECUTION_EXEMPT) | qualified == unmeasured
    assert all(why for why in exempt.values())
