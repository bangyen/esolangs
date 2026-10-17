"""Generator capabilities and conventions every generator follows."""

import contextlib
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import esolangs
import esolangs.languages.generators as boolean
from esolangs.registry import LANGUAGES
from esolangs.runtime._evaluate import _evaluate
from tests.cli.test_cli import call_main
from tests.support.generator_support import probe_table
from tests.support.witness_tables import witnesses


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
def test_declared_arity_cap_is_enforced(name, cap) -> None:
    with pytest.raises(esolangs.GeneratorCapError):
        esolangs.generate(name, "0" * (1 << (cap + 1)))


@pytest.mark.parametrize(
    "name", sorted(name for name, lang in LANGUAGES.items() if lang.boolean)
)
def test_structured_witnesses_build_at_the_arity_cap(name) -> None:
    """Up to the cap (or 11), structured tables build or refuse by contract."""
    inputs = min(LANGUAGES[name].generator_max_inputs or 11, 11)
    for table in witnesses(inputs)[:-1]:  # the random witness is priced per language
        with contextlib.suppress(esolangs.GeneratorCapError):
            esolangs.generate(name, table)


#: Generators whose ``GeneratorCapError`` never reaches a caller.
_INTERNAL_CAPS = {name for name, lang in LANGUAGES.items() if lang.internal_cap}


def test_a_generator_that_can_refuse_declares_its_limit() -> None:
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


@pytest.mark.medium
@pytest.mark.parametrize(
    "name",
    sorted(
        {
            name
            for name, lang in LANGUAGES.items()
            if lang.generator_max_inputs or lang.generator_restrictions
        }
        | _INTERNAL_CAPS
    ),
)
def test_restricted_generators_have_executed_positive_controls(name) -> None:
    table = probe_table(name)
    assert (
        _evaluate(
            name, esolangs.generate(name, table), inputs=len(table).bit_length() - 1
        )
        == table
    )


@pytest.mark.medium
def test_list_exposes_limits_in_both_formats(capsys) -> None:
    text = call_main(["list", "--details"], capsys)
    for lang in LANGUAGES.values():
        if lang.generator_max_inputs is not None:
            assert f"max-inputs={lang.generator_max_inputs}" in text, lang.name
        if lang.generator_restrictions:
            assert lang.generator_restrictions in " ".join(text.split()), lang.name
    out = call_main(["list", "--details", "--json"], capsys)
    for row in json.loads(out):
        facts = esolangs.describe(row["name"])
        for field in ("generator_max_inputs", "generator_restrictions"):
            assert row[field] == facts[field]
