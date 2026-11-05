"""Certification policy cannot change backend operation."""

import importlib
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
    assert all(
        isinstance(load_certification(lang), CertificationSpec)
        for lang in LANGUAGES.values()
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
    assert module.LANGUAGE is original
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
for name in esolangs.list_languages():
    esolangs.describe(name)
program = esolangs.generate(sys.argv[1], '01')
assert esolangs.run(sys.argv[1], program, stdin='1') == '1'
try:
    import esolangs.registry._certification
except ImportError as error:
    assert str(error) == 'certification is not operational'
else:
    raise AssertionError('import barrier did not fire')
"""
    subprocess.run([sys.executable, "-c", code, REFERENCE], check=True, timeout=10)
