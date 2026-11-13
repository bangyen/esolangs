"""Generator capabilities and conventions every generator follows."""

import contextlib
import inspect
import json
from pathlib import Path

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import load as load_certification
from tests.support.cli_support import call_main
from tests.support.evaluation import _evaluate
from tests.support.generator_support import probe_table
from tests.support.witness_tables import witnesses


def test_boolean_generators_take_a_truth_table() -> None:
    """Each backend generator takes one typed request."""
    failures = {}
    for name, lang in LANGUAGES.items():
        if lang.backend is None:
            continue
        fn = lang.backend.generate
        params = list(inspect.signature(fn).parameters.values())
        issues = []
        if not params:
            issues.append("takes no arguments")
        elif params[0].name != "request":
            issues.append(f"first parameter is {params[0].name!r}")
        issues.extend(
            f"requires {param.name!r} beyond request"
            for param in params[1:]
            if param.default is inspect.Parameter.empty
        )
        if issues:
            failures[name] = issues
    assert not failures


@pytest.mark.parametrize(
    ("name", "cap"),
    [
        (name, lang.backend.max_inputs)
        for name, lang in LANGUAGES.items()
        if lang.backend is not None and lang.backend.max_inputs is not None
    ],
)
def test_declared_arity_cap_is_enforced(name, cap) -> None:
    with pytest.raises(esolangs.GeneratorCapError):
        esolangs.generate(name, "0" * (1 << (cap + 1)))


@pytest.mark.parametrize(
    "name", sorted(name for name, lang in LANGUAGES.items() if lang.backend)
)
def test_structured_witnesses_build_at_the_arity_cap(name) -> None:
    """Up to the cap (or 11), structured tables build or refuse by contract."""
    inputs = min(LANGUAGES[name].backend.max_inputs or 11, 11)
    for table in witnesses(inputs)[:-1]:  # the random witness is priced per language
        with contextlib.suppress(esolangs.GeneratorCapError):
            esolangs.generate(name, table)


#: Generators whose ``GeneratorCapError`` never reaches a caller.
_INTERNAL_CAPS = {
    name for name, lang in LANGUAGES.items() if load_certification(lang).internal_cap
}


def test_a_generator_that_can_refuse_declares_its_limit() -> None:
    """A ``GeneratorCapError`` a caller can see is in ``describe``."""
    undeclared = []
    for name, lang in LANGUAGES.items():
        if lang.backend is None or name in _INTERNAL_CAPS:
            continue
        module = Path(inspect.getfile(lang.backend.generate))
        files = module.parent.glob("*.py") if module.stem == "__init__" else [module]
        refuses = any("GeneratorCapError(" in f.read_text("utf-8") for f in files)
        declared = lang.backend.max_inputs or lang.backend.restrictions
        if refuses and not declared:
            undeclared.append(name)
    assert not undeclared, (
        f"{undeclared} raise GeneratorCapError; set max_inputs= or "
        "restrictions= in its BooleanBackend"
    )


@pytest.mark.medium
@pytest.mark.parametrize(
    "name",
    sorted(
        {
            name
            for name, lang in LANGUAGES.items()
            if lang.backend is not None
            and (lang.backend.max_inputs or lang.backend.restrictions)
        }
        | _INTERNAL_CAPS
    ),
)
def test_restricted_generators_have_executed_positive_controls(name) -> None:
    table = probe_table(name)
    assert (
        _evaluate(
            name,
            esolangs.generate(name, table),
            inputs=len(table).bit_length() - 1,
        )
        == table
    )


@pytest.mark.medium
def test_list_exposes_limits_in_both_formats(capsys) -> None:
    text = call_main(["list", "--details"], capsys)
    for lang in LANGUAGES.values():
        if lang.backend is None:
            continue
        if lang.backend.max_inputs is not None:
            assert f"max-inputs={lang.backend.max_inputs}" in text, lang.name
        if lang.backend.restrictions:
            assert lang.backend.restrictions in " ".join(text.split()), lang.name
    out = call_main(["list", "--details", "--json"], capsys)
    for row in json.loads(out):
        facts = esolangs.describe(row["name"])
        for field in ("generator_max_inputs", "generator_restrictions"):
            assert row[field] == getattr(facts, field)
