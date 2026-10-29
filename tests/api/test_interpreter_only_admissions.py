"""Admission routes, and API and VM integration for the interpreter-only three."""

from datetime import datetime

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.vm import make_vm
from scripts.docs.curation import FAME_BACKLINKS
from scripts.docs.curation import rows as _curation_rows
from tests.support.generator_support import CHECK
from tests.support.pick import languages
from tests.support.samples import SAMPLES

_CENSUS = _curation_rows()


def test_every_language_was_admitted_by_a_recorded_route() -> None:
    """Fame is ``FAME_BACKLINKS`` backlinks; below, only a first implementation."""
    unrecorded = sorted(set(LANGUAGES) - set(_CENSUS))
    assert not unrecorded, f"no admission record for {unrecorded}; {CHECK}"
    stale = sorted(set(_CENSUS) - set(LANGUAGES))
    assert not stale, f"remove {stale} from its package's [curation] section"
    for name, row in _CENSUS.items():
        if row.get("unassessed"):
            continue  # offline; `finish` asks for the count before merging
        # The route is derived: fame at ``FAME_BACKLINKS``, else first impl.
        assert isinstance(row["backlinks"], int), name


def test_every_first_implementation_was_one_when_admitted() -> None:
    """Below fame: an admission date, nothing outside before it, a generator.

    The facts are fixed at the original admission, so membership is
    recomputable from them alone (docs/limitations.md, Curation).
    """
    for name, row in _CENSUS.items():
        if row.get("unassessed") or row["backlinks"] >= FAME_BACKLINKS:
            continue
        admitted = row.get("admitted")
        assert isinstance(admitted, datetime), f"{name}: record [curation] admitted"
        outside = row.get("outside_implementation")
        if outside is not None:
            when = outside["date"]
            if not isinstance(when, datetime):
                admitted, when = admitted.date(), when  # a day: strict order only
                assert when != admitted, f"{name}: same day; record the time"
            assert when > admitted, f"{name}: implemented elsewhere first"
        # Interpreter-only is the fame route's alone.
        assert esolangs.describe(name)["boolean_generator"], name


@pytest.mark.parametrize("language", languages(boolean_generator=False))
def test_api_and_vm(language: str) -> None:
    code, stdin = SAMPLES[language]
    output = esolangs.run(language, code, stdin=stdin)
    vm = make_vm(language, code, stdin=stdin)
    while not vm.halted:
        hash(vm.snapshot())
        vm.step()
    assert vm.output == output
    final = vm.snapshot()
    vm.step()
    assert vm.snapshot() == final
    assert esolangs.describe(language)["boolean_generator"] is False
    with pytest.raises(ValueError, match="no boolean generator"):
        esolangs.generate(language, "01")
