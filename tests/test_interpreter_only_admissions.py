"""Admission routes, and API and VM integration for the interpreter-only three."""

import json
from pathlib import Path

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.vm import make_vm

_CENSUS = json.loads(
    (Path(__file__).parent / "fixtures/curation.json").read_text(encoding="utf-8")
)["languages"]


def test_every_language_was_admitted_by_a_recorded_route() -> None:
    """Fame is 60 backlinks; below that, a first implementation or one of six."""
    assert set(_CENSUS) == set(LANGUAGES)
    for name, row in _CENSUS.items():
        assert (row["route"] == "fame") == (row["backlinks"] >= 60), name
        assert row["route"] in {"fame", "first implementation", "grandfathered"}
    grandfathered = {
        name for name, row in _CENSUS.items() if row["route"] == "grandfathered"
    }
    assert grandfathered == {"123", "BF-PDA", "BIO", "Jaune", "NoComment", "Sophie"}


@pytest.mark.parametrize(
    ("language", "code", "stdin", "output"),
    [
        ("HQ9+", "h+q", "unused", "Hello, world!\nh+q"),
        ("Nope.", "", "unused", "Nope."),
        ("Unary", "0" * 108, "Z", "Z"),
    ],
)
def test_api_and_vm(language: str, code: str, stdin: str, output: str) -> None:
    assert esolangs.run(language, code, stdin) == output
    vm = make_vm(language, code, stdin)
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


def test_unary_generator_refusal_does_not_deny_runtime_input() -> None:
    with pytest.raises(esolangs.ArgumentError, match="generator contracts") as caught:
        esolangs.generate("Unary", "01")
    assert "reads no input" not in str(caught.value)
