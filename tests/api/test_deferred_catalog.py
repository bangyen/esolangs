"""Catalog metadata stays usable with deferred generator imports blocked."""

import subprocess
import sys

import pytest


@pytest.mark.medium
def test_catalog_defers_implementations_until_generation():
    code = """
import importlib.abc
import inspect
import sys
from dataclasses import replace

import esolangs
from esolangs import registry
from esolangs.registry._functions import FunctionRef
from tests.support.evaluation import _evaluate

pilots = [lang for lang in registry.LANGUAGES.values()
          if lang.backend is not None
          and isinstance(lang.backend.entrypoint, FunctionRef)]
assert pilots, 'no deferred descriptor exercised'
assert 'GENERATORS' not in dir(registry)
assert not hasattr(registry, 'GENERATORS')
modules = {lang.backend.entrypoint.module for lang in pilots}
assert not modules.intersection(sys.modules), 'pilot imported during initialization'

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in modules:
            raise ImportError('deferred import control')

block = Block()
sys.meta_path.insert(0, block)
try:
    esolangs.list_languages()
    before = [esolangs.describe(name) for name in esolangs.list_languages()]
    assert not modules.intersection(sys.modules), 'catalog imported a pilot'
    try:
        esolangs.generate(pilots[0].name, '00110101')
    except ImportError as error:
        assert 'deferred import control' in str(error)
    else:
        raise AssertionError('blocking control did not fire')
finally:
    sys.meta_path.remove(block)

assert 'generators' not in dir(esolangs.languages)
assert not hasattr(esolangs.languages, 'generators')
try:
    importlib.import_module('esolangs.languages.generators')
except ModuleNotFoundError as error:
    assert error.name == 'esolangs.languages.generators'
else:
    raise AssertionError('retired generator facade imported')
for lang in pilots:
    backend = lang.backend
    generate = backend.generate
    module = sys.modules[generate.__module__]
    assert getattr(module, generate.__name__) is generate
    assert not hasattr(module, 'LANGUAGE')
    assert inspect.getsourcefile(generate) == module.__file__
    assert (tuple(inspect.signature(generate).parameters)
            == backend.entrypoint.parameters)
    assert replace(backend, entrypoint=generate).generate is generate
    assert registry.LANGUAGES[lang.name].backend.generate is generate
sample = next(lang for lang in pilots if not lang.parameterized
              and lang.backend.max_inputs is None
              and lang.runtime.source_kind.value == 'text')
program = esolangs.generate(sample.name, '00110101')
assert _evaluate(sample.name, program, inputs=3) == '00110101'
assert [esolangs.describe(name) for name in esolangs.list_languages()] == before
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
