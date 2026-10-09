"""Generator capabilities and conventions every generator follows."""

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import esolangs
import esolangs.tools as boolean
from esolangs._evaluate import _evaluate
from esolangs.registry import LANGUAGES
from tests.cli.test_cli import call_main


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


@pytest.mark.parametrize(
    ("name", "cap"),
    [
        (name, lang.generator_max_inputs)
        for name, lang in LANGUAGES.items()
        if lang.generator_max_inputs is not None
    ],
)
def test_declared_arity_cap_is_enforced(name, cap):
    with pytest.raises(esolangs.GeneratorCapError):
        esolangs.generate(name, "0" * (1 << (cap + 1)))


#: Generators whose ``GeneratorCapError`` never reaches a caller, and why.
_INTERNAL_CAPS = {
    "6-5": "the stream-ordered tree is tried only when its labels fit",
}


def test_a_generator_that_can_refuse_declares_its_limit():
    """A ``GeneratorCapError`` a caller can see is in ``describe``."""
    undeclared = []
    for name, lang in LANGUAGES.items():
        if lang.boolean is None or name in _INTERNAL_CAPS:
            continue
        module = Path(inspect.getfile(lang.boolean))
        files = module.parent.glob("*.py") if module.stem == "__init__" else [module]
        refuses = any("GeneratorCapError(" in f.read_text("utf-8") for f in files)
        declared = lang.generator_max_inputs or lang.generator_restrictions
        if refuses and not declared:
            undeclared.append(name)
    assert not undeclared, (
        f"{undeclared} raise GeneratorCapError; set generator_max_inputs= or "
        "generator_restrictions= in its LANGUAGE"
    )
    assert _INTERNAL_CAPS.keys() <= LANGUAGES.keys()


@pytest.mark.medium
@pytest.mark.parametrize("name", ["Befunge", "Malbolge", "6-5", "Polynomial"])
def test_restricted_generators_have_executed_positive_controls(name):
    assert _evaluate(name, esolangs.generate(name, "0110"), inputs=2) == "0110"


def test_internal_route_budget_is_not_a_generator_restriction():
    assert esolangs.describe("6-5")["generator_restrictions"] is None
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
