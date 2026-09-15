"""Every deep proof declares a cost band, and every band keeps its bargain.

``tests/proofs/deep/__main__.py`` selects proofs by a ``BAND`` they declare
rather than by the paths its three consumers used to hardcode.  That is a
better arrangement only while the declarations stay honest: a band is a claim
about cost, and an indirection that decides what runs is also an easy way to
stop running something.

The failure being guarded against is not hypothetical.  ``_DOCUMENTED_SIZES``
pinned COD at 942,692 characters through the commit that linearized it to 294,
and nothing failed, because the test holding it carries the ``slow`` marker and
PR CI does not run it.  A mislabelled band would look exactly the same: green,
fast, and not checking anything.

These are cheap -- importing six modules and reading two constants runs no
proof -- so the file stays in the fast band and gates every push.
"""

from __future__ import annotations

import itertools

import pytest

from tests.proofs.deep.__main__ import BANDS, BUDGET, Proof, discover, selected

#: The proofs that must gate locally.  Pinned deliberately, and the one place
#: in this repository where a duplicated list is the right answer: demoting a
#: proof out of ``verify`` should cost a second, visible edit rather than
#: happening as a side effect of editing the proof.
_VERIFY_BAND = frozenset({"arrowqueue", "bio"})


@pytest.fixture(scope="module")
def proofs() -> list[Proof]:
    """Every deep proof, discovered once."""
    return discover()


def test_every_deep_proof_declares_a_band(proofs: list[Proof]) -> None:
    """Discovery asserts this per module; this pins that any were found."""
    assert len(proofs) >= 6
    assert all(proof.band in BANDS for proof in proofs)
    assert all(proof.cost > 0 for proof in proofs)


def test_the_directory_has_no_unregistered_proof(proofs: list[Proof]) -> None:
    """Every plainly-named file under deep/ is a registered proof.

    Discovery treats a leading underscore as "helper".  That convention is
    what stops a new support module from failing the run, and this is the
    other half of it: a file without an underscore is a proof, and a proof
    the runner does not know about is one nothing runs.
    """
    from pathlib import Path

    import tests.proofs.deep as package

    on_disk = {
        path.stem
        for path in Path(package.__path__[0]).glob("*.py")
        if not path.stem.startswith("_")
    }
    assert on_disk == {proof.name for proof in proofs}


def test_each_band_stays_inside_its_budget() -> None:
    """A band is a cost claim, so the claim is checked.

    Cumulative, matching how the runner selects: the ``ci`` budget covers the
    ``verify`` proofs it also runs.
    """
    for band in BANDS:
        total = sum(proof.cost for proof in selected(band))
        assert total <= BUDGET[band], (
            f"band {band!r} declares {total:.1f}s against a {BUDGET[band]}s budget"
        )


def test_the_local_gate_runs_exactly_the_cheap_proofs(proofs: list[Proof]) -> None:
    """Demoting a proof out of the local gate must be a deliberate edit."""
    assert {p.name for p in proofs if p.band == "verify"} == _VERIFY_BAND


def test_bands_are_cumulative(proofs: list[Proof]) -> None:
    """Selecting a band runs it and every band that runs more often."""
    names = [{p.name for p in selected(band)} for band in BANDS]
    for narrower, wider in itertools.pairwise(names):
        assert narrower < wider
    assert {p.name for p in selected("all")} == {p.name for p in proofs}


def test_every_proof_is_callable_with_no_arguments(proofs: list[Proof]) -> None:
    """The runner calls ``main()`` bare, so a required parameter would break it.

    ArrowQueue takes flags of its own and read ``sys.argv`` directly, which
    made argparse reject the band name and exit 2 before a lemma ran.
    """
    import inspect

    for proof in proofs:
        signature = inspect.signature(proof.module.main)
        required = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind not in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
        ]
        assert not required, f"{proof.name}.main() requires {required}"
