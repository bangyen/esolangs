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
from esolangs.languages import generators
from esolangs.registry._backend import DeferredBackend
from tests.support.evaluation import _evaluate

pilots = [lang for lang in registry.LANGUAGES.values()
          if isinstance(lang.backend, DeferredBackend)]
assert pilots, 'no deferred descriptor exercised'
assert 'GENERATORS' in dir(registry)
modules = {object.__getattribute__(lang.backend, 'generate').module for lang in pilots}
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

for lang in pilots:
    backend = lang.backend
    generate = backend.generate
    module = sys.modules[generate.__module__]
    assert getattr(module, generate.__name__) is generate
    assert getattr(generators, generate.__name__) is generate
    assert generate.__name__ in dir(generators)
    assert module.LANGUAGE is lang
    assert inspect.getsourcefile(generate) == module.__file__
    assert ('width' in inspect.signature(generate).parameters) == backend.width_aware
    assert replace(backend, generate=generate).generate is generate
    program = esolangs.generate(lang.name, '00110101')
    assert _evaluate(lang.name, program, inputs=3) == '00110101'
assert [esolangs.describe(name) for name in esolangs.list_languages()] == before
assert isinstance(registry.GENERATORS, dict)
assert registry.GENERATORS[pilots[0].name] is pilots[0].backend.generate
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
