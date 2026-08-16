"""Unit tests for the canonical language identifiers."""

import importlib

from esolangs.registry import LANGUAGES, canonical_id


def test_every_language_has_a_canonical_id() -> None:
    """Each language's ``id`` is a non-empty, valid-Python-identifier slug."""
    for name, lang in LANGUAGES.items():
        assert lang.id, name
        assert lang.id.isidentifier(), name


def test_canonical_id_derives_the_recorded_id() -> None:
    """The recorded id is exactly what ``canonical_id`` derives from the name."""
    for name, lang in LANGUAGES.items():
        assert canonical_id(name) == lang.id, name


def test_canonical_id_is_a_valid_identifier() -> None:
    """The function produces valid-Python-identifier slugs for every name."""
    for name in LANGUAGES:
        assert canonical_id(name).isidentifier(), name


def test_id_matches_the_interpreter_module() -> None:
    """The canonical id is the interpreter module's last component."""
    for name, lang in LANGUAGES.items():
        if lang.interpreter:
            assert lang.id == lang.interpreter.split(".")[-1], name


def test_id_matches_the_generator_function() -> None:
    """The canonical id is also the generator function's name."""
    for name, lang in LANGUAGES.items():
        if lang.generator:
            assert lang.id == lang.generator.__name__, name


def test_modules_are_importable_under_their_id() -> None:
    """Every interpreter module path resolves to a real module."""
    for name, lang in LANGUAGES.items():
        if lang.interpreter:
            module = importlib.import_module(
                "esolangs.interpreters." + lang.interpreter
            )
            assert hasattr(module, "run"), name
