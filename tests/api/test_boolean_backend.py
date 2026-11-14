"""Boolean backend absence and field ownership are explicit."""

from dataclasses import fields, replace

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._language import LanguageDeclaration
from esolangs.runtime._definition import RuntimeSpec


def test_backend_fields_have_one_owner():
    names = {field.name for field in fields(BooleanBackend)}
    for record in (LanguageDeclaration, RuntimeSpec, CertificationSpec):
        assert names.isdisjoint(field.name for field in fields(record))
    assert all(
        lang.backend is None or isinstance(lang.backend, BooleanBackend)
        for lang in LANGUAGES.values()
    )


@pytest.mark.parametrize(
    "language", [name for name, lang in LANGUAGES.items() if lang.backend is None]
)
def test_interpreter_only_contract_adapters_remain_available(language):
    assert not LANGUAGES[language].parameterized
    assert esolangs.read_answer(language, "0") == "0"
    assert esolangs.read_answer(language, "1") == "1"
    with pytest.raises(esolangs.ArgumentError, match="no boolean generator"):
        esolangs.generate(language, "01")
    with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
        esolangs.encode_inputs(language, [1])


def test_backend_constructor_and_replacement_use_only_entrypoint():
    backend = BooleanBackend(str, max_inputs=3, no_wrap="one line")
    changed = replace(backend, entrypoint=repr)
    assert (backend.generate, changed.generate) == (str, repr)
    assert (changed.max_inputs, changed.no_wrap) == (3, "one line")
    for values in ({}, {"generate": str}):
        with pytest.raises(TypeError):
            BooleanBackend(**values)
    with pytest.raises(TypeError):
        replace(backend, generate=repr)
    with pytest.raises(ValueError, match="callable generator"):
        BooleanBackend(entrypoint=None)
    with pytest.raises(ValueError, match="callable generator"):
        replace(backend, entrypoint=None)
