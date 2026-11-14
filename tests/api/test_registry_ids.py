"""Canonical language identifiers and aliases."""

import importlib

import pytest

from esolangs.registry import LANGUAGES, resolve
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._slug import canonical_id
from esolangs.runtime._capabilities import MachineCapabilities
from esolangs.runtime._definition import RuntimeSpec


def test_catalog_identifiers_resolve_and_keep_their_owned_namespace() -> None:
    from esolangs import languages

    for name, lang in LANGUAGES.items():
        assert lang.id, name
        assert lang.id.isidentifier(), name
        if lang.runtime.interpreter:
            assert lang.id == lang.runtime.interpreter.split(".")[-1], name
        package = importlib.import_module(f"esolangs.languages.{lang.id}")
        assert getattr(languages, lang.id) is package
        for spelling in (name, name.casefold(), lang.id, *lang.aliases):
            assert resolve(spelling) == name, spelling
        if lang.backend is not None:
            generator = importlib.import_module(
                f"esolangs.languages.{lang.id}.generator"
            )
            fn = lang.backend.generate
            assert getattr(generator, fn.__name__) is fn
            assert fn.__name__ == f"{lang.id}_request", name


def test_a_slug_drops_only_punctuation_the_language_has() -> None:
    """``Piet++`` is another wiki language; slugged onto Piet, it ran Piet."""
    from esolangs.exceptions import UnknownLanguageError

    for name, lang in LANGUAGES.items():
        bare = "".join(c if c.isalnum() else " " for c in name)
        if canonical_id(bare) == lang.id:
            assert resolve(bare) == name, bare
        if "+" not in name + "".join(lang.aliases):
            if name + "++" in LANGUAGES:
                assert resolve(name + "++") == name + "++"
            else:
                with pytest.raises(UnknownLanguageError):
                    resolve(name + "++")
        # Whitespace and dashes are separators, not symbols to own.
        assert resolve(f"\t{lang.id}\n") == name, lang.id
        assert resolve(name.replace(" ", "\xa0").replace("-", "\u2013")) == name


def test_a_language_cannot_both_wrap_and_refuse_to() -> None:
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._language import LanguageDeclaration

    with pytest.raises(ValueError, match="exclude each other"):
        LanguageDeclaration(
            "X",
            runtime=RuntimeSpec(
                "fixture",
                machine_preparation="prepare_machine",
                completion_entrypoint="_execute",
                capabilities=MachineCapabilities(),
            ),
            backend=BooleanBackend(
                entrypoint=str, wrap=wrap_chars, no_wrap="a break changes it"
            ),
        )


def test_parameterized_follows_the_backend_independently_of_examples() -> None:
    from dataclasses import replace

    from esolangs.registry._backend import TemplateSpec
    from esolangs.registry._language import Example, LanguageDeclaration

    embedded = LanguageDeclaration(
        "X",
        runtime=RuntimeSpec(
            "fixture",
            machine_preparation="prepare_machine",
            completion_entrypoint="_execute",
            capabilities=MachineCapabilities(),
        ),
        backend=BooleanBackend(entrypoint=str, template=TemplateSpec(pair=("a", "b"))),
    )
    assert embedded.parameterized
    assert replace(embedded, example=Example(table="01", bits=(1,))).parameterized
    reader = LanguageDeclaration(
        "X",
        runtime=RuntimeSpec(
            "fixture",
            machine_preparation="prepare_machine",
            completion_entrypoint="_execute",
            capabilities=MachineCapabilities(),
        ),
        example=Example(table="01", bits=(1,)),
    )
    assert not reader.parameterized
