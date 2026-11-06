"""Certification policy cannot change backend operation."""

import ast
import importlib
import inspect
import subprocess
import sys
from dataclasses import fields

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._certification import load as load_certification
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec
from tests.support.pick import languages


def test_certification_facts_have_one_owner(monkeypatch):
    names = {field.name for field in fields(CertificationSpec)}
    assert names.isdisjoint(field.name for field in fields(Language))
    assert names.isdisjoint(field.name for field in fields(RuntimeSpec))
    assert "certification" not in {field.name for field in fields(Language)}
    for lang in LANGUAGES.values():
        record = load_certification(lang)
        assert isinstance(record, CertificationSpec)
        if record.payload is not None:
            assert (
                record.payload.__module__
                == f"esolangs.languages.{lang.id}.certification"
            )

    from types import SimpleNamespace

    from esolangs.registry import _certification
    from tests.support.reference import REFERENCE

    monkeypatch.setattr(
        _certification,
        "import_module",
        lambda _name: SimpleNamespace(CERTIFICATION=None),
    )
    with pytest.raises(TypeError, match="CertificationSpec"):
        load_certification(LANGUAGES[REFERENCE])

    def broken(_name):
        raise ModuleNotFoundError(
            "missing evidence dependency", name="evidence_dependency"
        )

    monkeypatch.setattr(_certification, "import_module", broken)
    with pytest.raises(ModuleNotFoundError, match="missing evidence dependency"):
        load_certification(LANGUAGES[REFERENCE])


@pytest.mark.parametrize("language", languages(boolean_generator=True))
def test_clearing_certification_preserves_generated_source(language, monkeypatch):
    original = LANGUAGES[language]
    module = importlib.import_module(original.backend.generate.__module__)
    assert not hasattr(module, "LANGUAGE")
    tree = ast.parse(inspect.getsource(module))
    reads = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert not {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.endswith(".descriptor")
        for alias in node.names
        if (alias.asname or alias.name) not in reads
    }
    before = esolangs.dump_program(language, esolangs.generate(language, "01"))
    path = f"esolangs.languages.{original.id}.certification"
    load_certification(original)
    if path in sys.modules:
        monkeypatch.setattr(sys.modules[path], "CERTIFICATION", CertificationSpec())
    after = esolangs.dump_program(language, esolangs.generate(language, "01"))
    assert after == before


@pytest.mark.medium
def test_operational_catalog_and_execution_do_not_import_certification():
    from tests.support.reference import REFERENCE

    code = """
import importlib.abc
import sys
class Barrier(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.endswith(('._certification', '.certification')):
            raise ImportError('certification is not operational')
barrier = Barrier()
sys.meta_path.insert(0, barrier)
import esolangs
from esolangs.registry import LANGUAGES
generated = 0
for name in esolangs.list_languages():
    esolangs.describe(name)
    language = LANGUAGES[name]
    if language.backend is None:
        continue
    artifact = esolangs.generate(name, '01')
    restored = esolangs.load_program(name, esolangs.dump_program(name, artifact))
    assert restored == artifact, name
    if language.parameterized:
        esolangs.instantiate(name, restored, [1])
    generated += 1
assert generated == sum(lang.backend is not None for lang in LANGUAGES.values()) > 0
program = esolangs.generate(sys.argv[1], '01')
assert esolangs.run(sys.argv[1], program, stdin='1').output == '1'
try:
    import esolangs.registry._certification
except ImportError as error:
    assert str(error) == 'certification is not operational'
else:
    raise AssertionError('import barrier did not fire')
"""
    subprocess.run([sys.executable, "-c", code, REFERENCE], check=True, timeout=10)
