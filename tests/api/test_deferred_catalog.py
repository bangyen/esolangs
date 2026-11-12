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
from esolangs.operations.source import _read_source
import pytest
from esolangs import registry
from esolangs.registry._backend import Generator
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import SourceKind
from tests.support.evaluation import _evaluate

assert registry.Generator is Generator and registry.SourceKind is SourceKind
pilots = [lang for lang in registry.LANGUAGES.values()
          if lang.backend is not None
          and isinstance(lang.backend.entrypoint, OperationRef)]
assert pilots, 'no deferred descriptor exercised'
modules = {lang.backend.entrypoint.module for lang in pilots}
native_modules = set(registry.INTERPRETERS.values())
blocked = modules | native_modules
assert not modules.intersection(sys.modules), 'pilot imported during initialization'

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in blocked:
            raise ImportError('deferred import control')

block = Block()
sys.meta_path.insert(0, block)
try:
    esolangs.list_languages()
    assert not modules.intersection(sys.modules), 'catalog imported a pilot'
    for name, language in registry.LANGUAGES.items():
        source = (esolangs.Raster((((0, 0, 0),),))
                  if language.runtime.source_kind.value == 'raster' else '')
        _read_source(name, source)
    assert not native_modules.intersection(sys.modules), 'source imported runner'
    with pytest.raises(ImportError, match='deferred import control'):
        importlib.import_module(next(iter(native_modules)))
    blocked = modules
    before = [esolangs.describe(name) for name in esolangs.list_languages()]
    with pytest.raises(ImportError, match='deferred import control'):
        esolangs.generate(pilots[0].name, '00110101')
finally:
    sys.meta_path.remove(block)

for lang in pilots:
    backend = lang.backend
    generate = backend.generate
    module = sys.modules[generate.__module__]
    assert getattr(module, generate.__name__) is generate
    assert inspect.getsourcefile(generate) == module.__file__
    assert (tuple(inspect.signature(generate).parameters)
            == ('request',))
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
