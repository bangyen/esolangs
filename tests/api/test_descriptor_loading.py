"""Catalog operations leave implementations unloaded until selected."""

import dataclasses
import inspect
import json
import subprocess
import sys

import pytest

from esolangs.generation.requests import GenerationRequest
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import load as load_certification
from esolangs.registry._functions import FunctionRef
from esolangs.registry._operations import OperationRef
from tests.support.reference import REFERENCE


@pytest.mark.medium
def test_catalog_does_not_import_generators():
    code = """
import esolangs, json, sys, typing
assert 'esolangs.registry' not in sys.modules
from esolangs._dialect import DialectSchema
schema = DialectSchema('detached_scope', {'mode': ('a', 'b')}, {'mode': 'a'})
settings = esolangs.DialectSettings(schema, mode='b')
values = [
    esolangs.ProgramArtifact('', 'detached_scope', settings),
    esolangs.Raster((((0, 0, 0),),)),
    esolangs.CompressedText.from_chunks(['x']),
    esolangs.TemplateArtifact('$', 'detached_scope',
        esolangs.TemplateBindings(setters=(('0','1'),))),
]
assert values[-1].fill([1]).source == '1'
for value in values:
    typing.get_type_hints(type(value))
assert 'esolangs.registry' not in sys.modules, 'value model loaded the catalog'
names = esolangs.list_languages()
assert 'esolangs.registry._table' in sys.modules, 'catalog control did not fire'
for name in names:
    esolangs.describe(name)
    esolangs.Language(name).settings().options()
def loaded():
    return sorted(m for m in sys.modules
                  if m.startswith("esolangs.languages.") and ".generator" in m)
assert not loaded(), loaded()
esolangs.generate(sys.argv[1], "01")
assert loaded(), "positive control did not load a generator"
print(json.dumps(names))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, REFERENCE],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert json.loads(completed.stdout) == sorted(LANGUAGES)


def test_declared_callable_parameters_match_implementations():
    def check(value):
        if isinstance(value, OperationRef):
            assert not hasattr(value, "parameters")
            assert tuple(inspect.signature(value.load()).parameters) == ("request",)
        elif isinstance(value, FunctionRef):
            assert not hasattr(value, "__signature__")
            target = value.load()
            assert callable(target)
            assert tuple(inspect.signature(target).parameters) == value.parameters, (
                value
            )
        elif dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                check(getattr(value, field.name))

    for language in LANGUAGES.values():
        check(language)
        check(load_certification(language))


def test_callable_references_observe_mutation(monkeypatch):
    reference = LANGUAGES[REFERENCE].backend.entrypoint
    assert isinstance(reference, OperationRef)
    original = reference.load()
    module = sys.modules[reference.module]
    monkeypatch.setattr(module, reference.name, lambda _table: "fault")
    assert reference(GenerationRequest("01")) == "fault"
    monkeypatch.setattr(module, reference.name, original)
    assert reference.load() is original


@pytest.mark.parametrize(
    "parameters", [[], ("width", "width"), ("bad-name",), ("class",), (None,)]
)
def test_callable_parameter_declarations_are_validated(parameters):
    with pytest.raises(ValueError, match="distinct identifiers"):
        FunctionRef("unloaded.module", "emit", parameters)


def test_backend_options_are_declared_without_loading():
    from esolangs.registry._backend import BooleanBackend

    plain = BooleanBackend(str, balance=str)
    assert not plain.layout_width
    assert not hasattr(plain, "balance_parameters")
    declared = BooleanBackend(
        OperationRef("unloaded.module", "emit"),
        layout_width=True,
        balance=OperationRef("unloaded.module", "balance"),
    )
    assert declared.layout_width
    assert not hasattr(declared.entrypoint, "parameters")
    with pytest.raises(TypeError, match="typed request"):
        BooleanBackend(FunctionRef("unloaded.module", "emit", ("table",)))
    assert "unloaded.module" not in sys.modules
