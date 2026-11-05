"""Runtime declarations have one owner and no compiler dependencies."""

import subprocess
import sys
from dataclasses import fields, replace
from pathlib import Path

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec


def test_runtime_facts_are_owned_only_by_the_runtime_record():
    runtime_fields = {field.name for field in fields(RuntimeSpec)}
    assert runtime_fields.isdisjoint(field.name for field in fields(Language))
    for lang in LANGUAGES.values():
        assert isinstance(lang.runtime, RuntimeSpec)
        assert lang.runtime.interpreter is not None


def test_backend_and_example_changes_preserve_the_runtime_definition():
    for lang in LANGUAGES.values():
        changed = replace(lang, boolean=None, template=None, example=Example())
        assert changed.runtime is lang.runtime
        assert changed.source_suffix == lang.source_suffix


@pytest.mark.medium
def test_runtime_schema_loads_with_all_package_imports_blocked():
    path = Path(esolangs.__file__).parent / "runtime/_definition.py"
    code = """
import importlib
import importlib.abc
import runpy
import sys

class Barrier(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'esolangs' or fullname.startswith('esolangs.'):
            raise ImportError('blocked package import')

sys.meta_path.insert(0, Barrier())
schema = runpy.run_path(sys.argv[1])
runtime = schema['RuntimeSpec']('standalone', split=True)
assert runtime.interpreter == 'standalone'
assert runtime.split
assert runtime.source_kind is schema['SourceKind'].TEXT
try:
    importlib.import_module('esolangs')
except ImportError as error:
    assert str(error) == 'blocked package import'
else:
    raise AssertionError('import barrier did not fire')
"""
    subprocess.run([sys.executable, "-c", code, str(path)], check=True, timeout=10)
