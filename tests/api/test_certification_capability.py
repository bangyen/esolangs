"""Certification policy cannot change backend operation."""

import importlib
from dataclasses import fields, replace

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec
from tests.support.pick import languages


def test_certification_facts_have_one_owner():
    names = {field.name for field in fields(CertificationSpec)}
    assert names.isdisjoint(field.name for field in fields(Language))
    assert names.isdisjoint(field.name for field in fields(RuntimeSpec))
    assert all(
        isinstance(lang.certification, CertificationSpec) for lang in LANGUAGES.values()
    )


@pytest.mark.parametrize("language", languages(boolean_generator=True))
def test_clearing_certification_preserves_generated_source(language, monkeypatch):
    original = LANGUAGES[language]
    module = importlib.import_module(original.backend.generate.__module__)
    assert module.LANGUAGE is original
    before = esolangs.dump_program(language, esolangs.generate(language, "01"))
    changed = replace(original, certification=CertificationSpec())
    assert changed.runtime is original.runtime
    assert changed.backend.generate is original.backend.generate
    assert changed.backend.template is original.backend.template
    monkeypatch.setitem(LANGUAGES, language, changed)
    monkeypatch.setattr(module, "LANGUAGE", changed)
    after = esolangs.dump_program(language, esolangs.generate(language, "01"))
    assert after == before
