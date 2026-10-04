"""Published capabilities agree with accepted and rejected generator inputs."""

import json

import pytest

import esolangs
from tests.test_cli import call_main


@pytest.mark.parametrize(("name", "cap"), [("Befunge", 13), ("Malbolge", 16)])
def test_declared_arity_cap_is_enforced(name, cap):
    assert esolangs.describe(name)["generator_max_inputs"] == cap
    with pytest.raises(esolangs.GeneratorCapError):
        esolangs.generate(name, "0" * (1 << (cap + 1)))


@pytest.mark.medium
@pytest.mark.parametrize("name", ["Befunge", "Malbolge", "6-5", "Polynomial"])
def test_restricted_generators_have_executed_positive_controls(name):
    assert esolangs.evaluate(name, esolangs.generate(name, "0110"), inputs=2) == "0110"


def test_internal_route_budget_is_not_a_generator_restriction():
    assert esolangs.describe("6-5")["generator_restrictions"] == ""
    assert esolangs.describe("6-5")["generator_max_inputs"] is None
    assert (
        "1934 instructions" in esolangs.describe("Polynomial")["generator_restrictions"]
    )
    assert (
        "1000000000 estimated characters"
        in esolangs.describe("Polynomial")["generator_restrictions"]
    )


@pytest.mark.medium
def test_list_exposes_limits_in_both_formats(capsys):
    text = call_main(["list", "--details"], capsys)
    assert "max-inputs=13" in text
    assert "1934 instructions" in text
    out = call_main(["list", "--details", "--json"], capsys)
    for row in json.loads(out):
        facts = esolangs.describe(row["name"])
        for field in ("generator_max_inputs", "generator_restrictions"):
            assert row[field] == facts[field]
