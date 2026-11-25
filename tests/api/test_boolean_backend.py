"""Boolean backend absence and field ownership are explicit."""

from dataclasses import fields, replace

import pytest

import esolangs
from esolangs.generation.wrap import wrap_chars
from esolangs.registry import LANGUAGES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._language import LanguageDeclaration
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from tests.support.reference import REFERENCE


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


def test_scoped_arity_cap_refuses_before_generation_or_layout() -> None:
    entered = []

    class Source(str):
        def __contains__(self, item):
            raise AssertionError("reflow inspected the source subclass")

    def generate(request):
        entered.append(request.table)
        return Source(",.")

    def balance(request):
        entered.append(request.table)
        return request.source

    record = LANGUAGES[REFERENCE]
    backend = BooleanBackend(generate, max_inputs=1, balance=balance, wrap=wrap_chars)
    scoped = esolangs.Catalog([replace(record, backend=backend)]).bind(REFERENCE)
    assert scoped.describe().generator_max_inputs == 1
    for layout in ({}, {"width": 1}, {"balance": True}):
        with pytest.raises(esolangs.GeneratorCapError, match="max-inputs=1, got 2"):
            scoped.generate("0110", **layout)
    assert entered == []
    program = scoped.generate("01", balance=True)
    assert entered == ["01", "01"]
    assert [scoped.evaluate(program, [bit]).answer for bit in (0, 1)] == ["0", "1"]
    wrapped = scoped.generate("01", width=1)
    assert type(wrapped.source) is str
    assert wrapped.source == ",\n."
    assert wrapped == esolangs.generate(
        REFERENCE, "01", width=1, catalog=scoped.catalog
    )
    assert [scoped.evaluate(wrapped, [bit]).answer for bit in (0, 1)] == ["0", "1"]


def test_arity_refusal_does_not_load_the_entrypoint() -> None:
    record = LANGUAGES[REFERENCE]
    backend = BooleanBackend(
        OperationRef("esolangs", "_absent_generator"), max_inputs=1
    )
    scoped = esolangs.Catalog([replace(record, backend=backend)]).bind(REFERENCE)
    with pytest.raises(esolangs.GeneratorCapError, match="max-inputs=1"):
        scoped.generate("0110")
    with pytest.raises(esolangs.ProgramError, match="_absent_generator"):
        scoped.generate("01")


@pytest.mark.parametrize("cap", [True, 0, -1, "2"])
def test_arity_caps_are_positive_integers(cap) -> None:
    with pytest.raises(ValueError, match="max_inputs must be a positive integer"):
        BooleanBackend(str, max_inputs=cap)
