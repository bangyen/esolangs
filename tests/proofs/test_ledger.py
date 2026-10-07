"""``docs/proofs/index.md`` must agree with the registry and with itself."""

from __future__ import annotations

import pytest

import esolangs
from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import (
    EXECUTION_CLASSES,
    FORMULA_CLAUSE_WORDS,
    LINEAR_CLAUSE_WORDS,
    NOT_A_LABEL,
    QUALIFIERS,
    SCALING_CLASSES,
    SCHEME_LABELS,
    WORKSPACE_CLASSES,
    Ledger,
    load,
)


@pytest.fixture(scope="module")
def ledger() -> Ledger:
    """The parsed ledger, read once for the module."""
    return load()


def test_the_ledger_covers_exactly_the_registered_generators(ledger: Ledger) -> None:
    """One row per callable in ``BY_BOOLEAN``, and no row without one."""
    registered = {lang.name for lang in BY_BOOLEAN.values()}
    listed = {row.generator for row in ledger.rows}
    assert listed == registered, (
        f"ledger-only: {sorted(listed - registered)}; "
        f"registry-only: {sorted(registered - listed)}"
    )


def test_every_row_has_a_distinct_generator(ledger: Ledger) -> None:
    """A duplicated row would let two different proofs claim one generator."""
    names = [row.generator for row in ledger.rows]
    assert len(names) == len(set(names)), "duplicate ledger rows"


def test_every_proof_label_is_defined(ledger: Ledger) -> None:
    """No row may cite a scheme the document does not define."""
    known = set(SCHEME_LABELS.values()) | QUALIFIERS
    used = {label for row in ledger.rows for label in row.labels}
    assert used <= known, f"undefined proof labels: {sorted(used - known)}"


def test_every_definition_is_a_label_or_declared_not_to_be(ledger: Ledger) -> None:
    """A ``**Heading.**`` in Proof schemes is a label, or is listed as not one."""
    accounted = set(SCHEME_LABELS) | NOT_A_LABEL
    assert ledger.defined_schemes <= accounted, (
        f"defined but unaccounted: {sorted(ledger.defined_schemes - accounted)}"
    )


def test_every_row_carries_exactly_one_scheme(ledger: Ledger) -> None:
    """A row proves its generator one way, or is an open exception."""
    for row in ledger.rows:
        expected = 0 if "exception" in row.labels else 1
        assert len(row.schemes) == expected, (
            f"{row.generator} has schemes {row.schemes}, expected {expected}"
        )


def test_every_row_says_something(ledger: Ledger) -> None:
    """An empty qualification is a row nobody finished."""
    for row in ledger.rows:
        assert row.qualification, f"{row.generator} has a blank qualification"


def test_capped_rows_match_the_resource_audit(ledger: Ledger) -> None:
    """Each ``cap`` row needs a lift argument, and each argument needs a row."""
    capped = ledger.labelled("cap")
    assert len(capped) == ledger.cap_bullets, (
        f"{len(capped)} cap rows against {ledger.cap_bullets} audit bullets"
    )
    for row in capped:
        assert row.generator in ledger.cap_section, (
            f"{row.generator} is capped but the resource audit never names it"
        )


def test_exception_rows_match_the_exceptions_section(ledger: Ledger) -> None:
    """Each ``exception`` row needs a gap written up, and vice versa."""
    exceptions = ledger.labelled("exception")
    assert len(exceptions) == ledger.exception_bullets, (
        f"{len(exceptions)} exception rows against {ledger.exception_bullets} bullets"
    )
    for row in exceptions:
        assert row.generator in ledger.exception_section, (
            f"{row.generator} is an exception but the section never names it"
        )


def test_the_ledger_totals_itself_correctly(ledger: Ledger) -> None:
    """The closing sentence's arithmetic must survive adding a language."""
    assert ledger.claimed_exceptions == len(ledger.labelled("exception"))
    assert ledger.claimed_arguments + ledger.claimed_exceptions == len(ledger.rows), (
        f"{ledger.claimed_arguments} + {ledger.claimed_exceptions} "
        f"!= {len(ledger.rows)} rows"
    )


def test_every_row_carries_a_scaling_cell(ledger: Ledger) -> None:
    """The Scaling column is checked like the Proof column: a class, then a clause."""
    for row in ledger.rows:
        assert row.scaling_class in SCALING_CLASSES, (
            f"{row.generator}: unknown scaling class {row.scaling_class!r}"
        )
        assert row.scaling_clause, f"{row.generator}: scaling cell has no clause"
        if row.scaling_class == "linear":
            words = len(row.scaling_clause.split())
            assert words <= LINEAR_CLAUSE_WORDS, (
                f"{row.generator}: linear clause is {words} words, "
                f"more than {LINEAR_CLAUSE_WORDS}"
            )


@pytest.mark.parametrize(
    ("column", "classes"),
    [("execution", EXECUTION_CLASSES), ("workspace", WORKSPACE_CLASSES)],
)
def test_every_row_carries_a_measured_cell(
    ledger: Ledger, column: str, classes: frozenset[str]
) -> None:
    """A known class, then what it bounds or why it is unmeasured."""
    for row in ledger.rows:
        kind = getattr(row, f"{column}_class")
        clause = getattr(row, f"{column}_clause")
        assert kind in classes, f"{row.generator}: unknown {column} class {kind!r}"
        assert clause, f"{row.generator}: {column} cell has no clause"
        words = len(clause.split())
        limit = (
            FORMULA_CLAUSE_WORDS
            if clause.startswith(("worst ", "at most "))
            else LINEAR_CLAUSE_WORDS
        )
        assert words <= limit, f"{row.generator}: {column} clause is {words} words"


def test_unproved_scaling_requires_a_totality_exception(ledger: Ledger) -> None:
    """An exception may still bound its construction on the supported domain."""
    measured = {row.generator for row in ledger.rows if row.scaling_class == "measured"}
    assert measured <= {row.generator for row in ledger.labelled("exception")}


def test_befunge_refusal_is_an_explicit_totality_exception(ledger: Ledger) -> None:
    """The fixed-torus refusal must not disappear from the totality audit."""
    with pytest.raises(esolangs.GeneratorCapError, match="at most thirteen inputs"):
        esolangs.generate("Befunge", "01" * 8192)
    assert "exception" in ledger.by_name()["Befunge"].labels
