"""Dialect settings: public surface, provenance, evaluation and per-language rules."""

import inspect
import pickle
from dataclasses import FrozenInstanceError

import pytest

import esolangs
from esolangs import DialectSettings, Raster
from esolangs import settings as settings_api
from esolangs.registry import LANGUAGES
from esolangs.registry._functions import FunctionRef
from esolangs.runtime import _execution
from esolangs.vm import make_vm
from tests.support.cli_support import call_both
from tests.support.dialect_support import (
    Unreadable,
    foreign_settings,
)
from tests.support.pick import languages
from tests.support.reference import REFERENCE


def _out_of_range() -> list[tuple[str, str, int | str]]:
    """A choice outside each dialect setting of every language."""
    cases = []
    for name in esolangs.list_languages():
        for key, item in esolangs.describe(name)["dialect_settings"].items():
            choice = item["choices"][-1]
            cases.append(
                (name, key, choice + 1 if isinstance(choice, int) else "bogus")
            )
    return cases


def _invalid() -> list[tuple[str, DialectSettings]]:
    """Out-of-range settings forged past the constructor, as an old pickle is.

    The constructor refuses them, so use must still re-validate.
    """
    cases = []
    for name, key, bad in _out_of_range():
        forged = DialectSettings()
        object.__setattr__(forged, "_items", ((key, bad),))
        cases.append((name, forged))
    return cases


def test_every_dialect_declares_its_values() -> None:
    """A language's ``dialect`` and ``dialect_values`` name the same settings."""
    for name, language in LANGUAGES.items():
        settings = (
            set(
                inspect.signature(
                    language.runtime.dialect.load()
                    if isinstance(language.runtime.dialect, FunctionRef)
                    else language.runtime.dialect
                ).parameters
            )
            if language.runtime.dialect is not None
            else set()
        )
        assert set(language.runtime.dialect_values or {}) == settings, name
        if settings:
            constructor = inspect.signature(
                _execution.interpreter_module(name)._Machine
            )
            assert language.runtime.dialect_defaults == {
                key: constructor.parameters[key].default for key in settings
            }, name


@pytest.mark.parametrize(
    ("language", "settings", "options"),
    [
        (REFERENCE, foreign_settings(), {}),
        (REFERENCE, foreign_settings(), {"isolated": True}),
        *[(name, settings, {}) for name, settings in _invalid()],
    ],
)
def test_invalid_settings_fail_before_reading(language, settings, options) -> None:
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(
            language, Unreadable(), stdin=Unreadable(), settings=settings, **options
        )
    with pytest.raises(esolangs.ArgumentError):
        make_vm(language, Unreadable(), stdin=Unreadable(), settings=settings)
    with pytest.raises(esolangs.ArgumentError):
        esolangs.generate(language, "01", settings=settings)


@pytest.mark.parametrize("operation", [esolangs.run, esolangs.generate])
def test_settings_require_the_public_object(operation, capsys) -> None:
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        operation(REFERENCE, Unreadable(), settings={})
    from esolangs.cli.args import _settings_of

    for value in (2, 3):
        document = '{"cell_modulus":2,"cell_modulus":' + str(value) + "}"
        with pytest.raises(SystemExit) as caught:
            _settings_of({"--settings": document})
        assert caught.value.code == 2
        assert "duplicate field" in capsys.readouterr().err
    assert _settings_of(
        {"--settings": '{"cell_modulus":255}'}, ["cell_modulus=256"]
    ) == esolangs.DialectSettings(cell_modulus=256)


def test_cli_help_shows_literal_settings_json(capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        call_both(["generate", "--help"], capsys)
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    from esolangs.cli.help import _capability_examples

    _template, dialects = _capability_examples()
    assert dialects
    assert dialects in help_text


@pytest.mark.parametrize("key", ["index_base", "eof", "input_framing"])
def test_omission_policies_are_not_public_choices(key) -> None:
    with pytest.raises(esolangs.ArgumentError, match="unknown dialect setting"):
        DialectSettings(**{key: "default"})


@pytest.mark.parametrize("balance", [False, True])
def test_raster_scaling_retains_settings(balance, native_png) -> None:
    raster, other = languages(source_kind="raster", boolean_generator=True)[:2]
    settings = DialectSettings()
    source = esolangs.generate(
        raster, "01", scale=2, balance=balance, settings=settings
    )
    assert source.settings is settings
    pixels = Raster.from_png(native_png(source))
    assert pixels.settings == settings
    retained = pixels.settings
    assert pixels.tagged(source.language).settings is retained
    assert pixels.upscaled(1).settings is retained
    assert pixels.upscaled(2).settings is retained
    assert pixels.tagged(other).settings is None


def test_inherited_choices_are_checked_before_input() -> None:
    source = esolangs.ProgramArtifact("+.", REFERENCE)
    object.__setattr__(source, "settings", foreign_settings())
    with pytest.raises(esolangs.ArgumentError, match="dialect settings"):
        esolangs.run(REFERENCE, source, stdin=Unreadable())


@pytest.mark.parametrize(
    "settings",
    [DialectSettings(), DialectSettings(expression_syntax="postfix")],
)
def test_settings_are_immutable_and_repr_rebuilds_them(
    settings: DialectSettings,
) -> None:
    """It printed ``DialectSettings(_items=(...))``, a private field."""
    assert eval(repr(settings), {"DialectSettings": DialectSettings}) == settings
    with pytest.raises(FrozenInstanceError):
        settings._items = ()


def test_default_pickle_has_no_retained_choices() -> None:
    source = esolangs.generate(REFERENCE, "01")
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings is None
    assert esolangs.run(REFERENCE, restored, stdin="1").output == "1"


def test_every_reported_default_and_choice_is_accepted(monkeypatch) -> None:
    def forbidden(*_args):
        raise AssertionError("dialect discovery reached")

    monkeypatch.setattr(inspect, "signature", forbidden)
    monkeypatch.setattr(_execution, "interpreter_module", forbidden)
    assert not hasattr(settings_api, "_dialect_keys")
    for language in esolangs.list_languages():
        schema = settings_api.dialect_choices(language)
        defaults = {key: item["default"] for key, item in schema.items()}
        assert DialectSettings(**defaults).options(language) == defaults
        for key, item in schema.items():
            for value in item["choices"]:
                selected = defaults | {key: value}
                assert DialectSettings(**selected).options(language) == selected
            choice = item["choices"][-1]
            invalid = choice + 1 if type(choice) is int else "bogus"
            for value in (None, invalid, True):
                with pytest.raises(esolangs.ArgumentError, match="choices: "):
                    DialectSettings(**{key: value})
