"""Catalog operations leave implementations unloaded until selected."""

import dataclasses
import inspect
import json
import subprocess
import sys

import pytest

from esolangs.registry import LANGUAGES
from esolangs.registry._certification import load as load_certification
from esolangs.registry._functions import FunctionRef
from tests.support.reference import REFERENCE


@pytest.mark.medium
def test_catalog_does_not_import_generators():
    code = """
import esolangs, json, sys
names = esolangs.list_languages()
for name in names:
    esolangs.describe(name)
    esolangs.DialectSettings().options(name)
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
        if isinstance(value, FunctionRef):
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
    assert isinstance(reference, FunctionRef)
    original = reference.load()
    module = sys.modules[reference.module]
    monkeypatch.setattr(module, reference.name, lambda _table: "fault")
    assert reference("01") == "fault"
    monkeypatch.setattr(module, reference.name, original)
    assert reference.load() is original
