"""Every deep proof declares a cost band, and every band keeps its bargain."""

from __future__ import annotations

import itertools

import pytest

from tests.proofs.deep.__main__ import BANDS, BUDGET, Proof, discover, selected

#: The proofs that must gate locally.  Pinned deliberately, and the one place
#: in this repository where a duplicated list is the right answer: demoting a
#: proof out of ``verify`` should cost a second, visible edit rather than
#: happening as a side effect of editing the proof.
_VERIFY_BAND = frozenset({"arrowqueue", "bio", "malbolge_packing"})


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
    """Every plainly-named file under deep/ is a registered proof."""
    from pathlib import Path

    import tests.proofs.deep as package

    on_disk = {
        path.stem
        for path in Path(package.__path__[0]).glob("*.py")
        if not path.stem.startswith("_")
    }
    assert on_disk == {proof.name for proof in proofs}


def test_each_band_stays_inside_its_budget() -> None:
    """A band is a cost claim, so the claim is checked."""
    for band in BANDS:
        total = sum(proof.cost for proof in selected(band))
        assert total <= BUDGET[band], (
            f"band {band!r} declares {total:.1f}s against a {BUDGET[band]}s budget"
        )


def test_the_local_gate_runs_exactly_the_cheap_proofs(proofs: list[Proof]) -> None:
    """Demoting a proof out of the local gate must be a deliberate edit."""
    # A proof that left with its language is no longer expected.
    present = {p.name for p in proofs}
    assert {p.name for p in proofs if p.band == "verify"} == _VERIFY_BAND & present


def test_bands_are_cumulative(proofs: list[Proof]) -> None:
    """Selecting a band runs it and every band that runs more often."""
    names = [{p.name for p in selected(band)} for band in BANDS]
    for narrower, wider in itertools.pairwise(names):
        assert narrower < wider
    assert {p.name for p in selected("all")} == {p.name for p in proofs}


def test_every_proof_is_callable_with_no_arguments(proofs: list[Proof]) -> None:
    """The runner calls ``main()`` bare, so a required parameter would break it."""
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
