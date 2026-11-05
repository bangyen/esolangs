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
        changed = replace(lang, backend=None, example=Example())
        assert changed.runtime is lang.runtime
        assert changed.source_suffix == lang.source_suffix


@pytest.mark.medium
@pytest.mark.parametrize(
    ("relative", "class_name"),
    [
        ("runtime/_definition.py", "RuntimeSpec"),
        ("registry/_certification.py", "CertificationSpec"),
    ],
)
def test_capability_schema_loads_with_all_package_imports_blocked(relative, class_name):
    path = Path(esolangs.__file__).parent / relative
    code = """
import importlib
import importlib.abc
import runpy
import sys
from dataclasses import is_dataclass, fields, FrozenInstanceError

class Barrier(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'esolangs' or fullname.startswith('esolangs.'):
            raise ImportError('blocked package import')

sys.meta_path.insert(0, Barrier())
schema = runpy.run_path(sys.argv[1])
record = schema[sys.argv[2]]()
assert is_dataclass(record)
field = fields(record)[0]
try:
    setattr(record, field.name, getattr(record, field.name))
except FrozenInstanceError:
    pass
else:
    raise AssertionError('schema record is mutable')
try:
    importlib.import_module('esolangs')
except ImportError as error:
    assert str(error) == 'blocked package import'
else:
    raise AssertionError('import barrier did not fire')
"""
    subprocess.run(
        [sys.executable, "-c", code, str(path), class_name], check=True, timeout=10
    )
