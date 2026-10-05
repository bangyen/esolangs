"""Generator capabilities and conventions every generator follows."""

import inspect
import json
from collections.abc import Callable
from typing import Any

import pytest

import esolangs
import esolangs.tools as boolean
from esolangs._evaluate import _evaluate
from tests.test_cli import call_main


def _public(module: object) -> list[tuple[str, Callable[..., Any]]]:
    """Return the public generator callables a package exports."""
    return [
        (name, getattr(module, name))
        for name in module.__all__
        if not name.startswith("_")
        and callable(getattr(module, name, None))
        and name not in {"instantiate", "main"}
    ]


def test_public_exports_resolve() -> None:
    """Every advertised export exists, including non-callable metadata."""
    for name in boolean.__all__:
        assert hasattr(boolean, name), name


def test_boolean_generators_take_a_truth_table() -> None:
    """Each generator takes ``truth_table`` and no required extra."""
    failures = {}
    exported = dict(_public(boolean))
    for name, fn in exported.items():
        params = list(inspect.signature(fn).parameters.values())
        issues = []
        if not params:
            issues.append("takes no arguments")
        elif params[0].name != "truth_table":
            issues.append(f"first parameter is {params[0].name!r}")
        issues.extend(
            f"requires {param.name!r} beyond truth_table"
            for param in params[1:]
            if param.default is inspect.Parameter.empty
        )
        if issues:
            failures[name] = issues
    assert not failures


@pytest.mark.parametrize(("name", "cap"), [("Befunge", 13), ("Malbolge", 16)])
def test_declared_arity_cap_is_enforced(name, cap):
    assert esolangs.describe(name)["generator_max_inputs"] == cap
    with pytest.raises(esolangs.GeneratorCapError):
        esolangs.generate(name, "0" * (1 << (cap + 1)))


@pytest.mark.medium
@pytest.mark.parametrize("name", ["Befunge", "Malbolge", "6-5", "Polynomial"])
def test_restricted_generators_have_executed_positive_controls(name):
    assert _evaluate(name, esolangs.generate(name, "0110"), inputs=2) == "0110"


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
