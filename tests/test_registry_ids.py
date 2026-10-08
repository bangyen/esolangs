import pytest

from esolangs.registry import LANGUAGES, canonical_id


def test_every_language_has_a_canonical_id() -> None:
    for name, lang in LANGUAGES.items():
        assert lang.id, name
        assert lang.id.isidentifier(), name


def test_canonical_id_derives_the_recorded_id() -> None:
    for name, lang in LANGUAGES.items():
        assert canonical_id(name) == lang.id, name


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
    from esolangs.registry._language import Language
    from esolangs.tools.wrap import wrap_chars

    with pytest.raises(ValueError, match="exclude each other"):
        Language("X", wrap=wrap_chars, no_wrap="a break changes it")
