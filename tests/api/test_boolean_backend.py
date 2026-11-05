"""Boolean backend absence and field ownership are explicit."""

from dataclasses import fields

import pytest

import esolangs
from esolangs import compat
from esolangs.registry import LANGUAGES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec


def test_backend_fields_have_one_owner():
    names = {field.name for field in fields(BooleanBackend)}
    for record in (Language, RuntimeSpec, CertificationSpec):
        assert names.isdisjoint(field.name for field in fields(record))
    assert all(
        lang.backend is None or isinstance(lang.backend, BooleanBackend)
        for lang in LANGUAGES.values()
    )


def test_a_present_backend_requires_a_generator():
    with pytest.raises(ValueError, match="callable generator"):
        BooleanBackend(entrypoint=None)


@pytest.mark.parametrize(
    "language", [name for name, lang in LANGUAGES.items() if lang.backend is None]
)
def test_interpreter_only_contract_adapters_remain_available(language):
    assert not LANGUAGES[language].parameterized
    assert esolangs.read_answer(language, "0") == "0"
    assert esolangs.read_answer(language, "1") == "1"
    with pytest.raises(esolangs.ArgumentError, match="no boolean generator"):
        compat.generate(language, "01")
    with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
        esolangs.encode_inputs(language, [1])


@pytest.mark.parametrize("keyword", ["generate", "entrypoint"])
def test_constructor_and_replacement_accept_both_generator_names(keyword):
    from dataclasses import replace

    backend = BooleanBackend(**{keyword: str}, max_inputs=3, no_wrap="one line")
    assert backend.generate is str
    changed = replace(backend, **{keyword: repr})
    assert changed.generate is repr
    assert (changed.max_inputs, changed.no_wrap) == (3, "one line")
    with pytest.raises(ValueError, match="callable generator"):
        BooleanBackend(**{keyword: None})
    with pytest.raises(ValueError, match="callable generator"):
        replace(backend, **{keyword: None})


def test_backend_still_requires_a_generator():
    with pytest.raises(TypeError, match="generator argument"):
        BooleanBackend()
