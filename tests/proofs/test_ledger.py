"""``docs/proofs.md`` must agree with the registry and with itself.

Nothing read the ledger before this file.  It is prose, so every claim in it
-- which generators it covers, which proof schemes exist, how many rows are
capped, how many exceptions remain -- was maintained by hand and verified by
hand.  The failure that motivates these tests is not hypothetical: thirteen
rows sat on a `tree` scheme for twenty-three commits after their generators
had been linearized onto lookups, and one row still does not match its
construction at all.

These are cheap on purpose.  Parsing a document and comparing name sets does
not run a generator, so the whole file stays in the fast band and gates every
push; the obligations that cost something live in ``test_schemes.py``.
"""

from __future__ import annotations

import pytest

from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import NOT_A_LABEL, QUALIFIERS, SCHEME_LABELS, Ledger, load


@pytest.fixture(scope="module")
def ledger() -> Ledger:
    """The parsed ledger, read once for the module."""
    return load()


def test_the_ledger_covers_exactly_the_registered_generators(ledger: Ledger) -> None:
    """One row per callable in ``BY_BOOLEAN``, and no row without one.

    Compared on the *display* name (``Language.name``), not the registry key:
    the keys are snake_case ids (``pct_squared_minus_one``) while the ledger
    names languages as they are written (``%^2^-1``).  Comparing the wrong one
    reports all 65 as missing in both directions, which reads like a parser
    bug rather than the naming mismatch it is.
    """
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
    """A ``**Heading.**`` in Proof schemes is a label, or is listed as not one.

    Checked in this direction only.  A defined scheme with no rows is fine --
    ``Reduction`` is defined and currently cited by qualifications rather than
    by the Proof column -- but a heading that is *neither* a label nor
    declared a note means the mapping has fallen behind a renamed definition.
    """
    accounted = set(SCHEME_LABELS) | NOT_A_LABEL
    assert ledger.defined_schemes <= accounted, (
        f"defined but unaccounted: {sorted(ledger.defined_schemes - accounted)}"
    )


def test_every_row_carries_exactly_one_scheme(ledger: Ledger) -> None:
    """A row proves its generator one way, or is an open exception.

    ``cap`` qualifies a scheme rather than replacing it, so a capped row still
    names one.  ``exception`` is the one label that stands alone: the row
    exists precisely because no scheme covers the generator yet, so demanding
    a scheme there would be demanding the gap be papered over.
    """
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
    """The closing sentence's arithmetic must survive adding a language.

    It states a count of totality arguments and a count of open exceptions.
    Adding a generator moves both the row count and, usually, only the first
    number -- so this is the assertion that catches a new language landing
    without the prose being revisited.
    """
    assert ledger.claimed_exceptions == len(ledger.labelled("exception"))
    assert ledger.claimed_arguments + ledger.claimed_exceptions == len(ledger.rows), (
        f"{ledger.claimed_arguments} + {ledger.claimed_exceptions} "
        f"!= {len(ledger.rows)} rows"
    )
