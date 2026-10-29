"""Canonical language identifiers and aliases."""

import importlib

import pytest

from esolangs.registry import LANGUAGES, resolve
from esolangs.registry._slug import canonical_id


def test_language_names_keep_their_package_namespace() -> None:
    from esolangs import languages

    for lang in LANGUAGES.values():
        package = importlib.import_module(f"esolangs.languages.{lang.id}")
        assert getattr(languages, lang.id) is package
        if lang.boolean is not None:
            generator = importlib.import_module(
                f"esolangs.languages.{lang.id}.generator"
            )
            assert getattr(generator, lang.boolean.__name__) is lang.boolean


def test_every_language_has_a_canonical_id() -> None:
    for name, lang in LANGUAGES.items():
        assert lang.id, name
        assert lang.id.isidentifier(), name


def test_every_name_id_and_alias_resolves_to_its_language() -> None:
    """Explicit ids and aliases must still resolve to the canonical name."""
    for name, lang in LANGUAGES.items():
        for spelling in (name, name.casefold(), lang.id, *lang.aliases):
            assert resolve(spelling) == name, spelling


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


def test_id_matches_the_interpreter_module() -> None:
    for name, lang in LANGUAGES.items():
        if lang.interpreter:
            assert lang.id == lang.interpreter.split(".")[-1], name


def test_id_matches_the_generator_function() -> None:
    """The canonical id is also the generator function's name."""
    for name, lang in LANGUAGES.items():
        if lang.boolean:
            fn = lang.boolean.__name__
            assert fn in (lang.id, lang.id.replace("_", "")), name


def test_a_language_cannot_both_wrap_and_refuse_to() -> None:
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._language import Language

    with pytest.raises(ValueError, match="exclude each other"):
        Language("X", wrap=wrap_chars, no_wrap="a break changes it")


def test_parameterized_follows_the_example() -> None:
    from esolangs.registry._language import Example, Language

    assert Language("X", example=Example(pair=("a", "b"))).parameterized
    assert not Language("X").parameterized
