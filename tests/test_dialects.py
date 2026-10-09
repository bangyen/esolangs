"""Dialect settings: public surface, provenance, evaluation and per-language rules."""

import pickle
from dataclasses import FrozenInstanceError
from io import StringIO

import pytest

import esolangs
from esolangs import DialectSettings, Raster
from esolangs.tagged import _Tagged
from esolangs.vm import make_vm
from tests.cli_support import call_both
from tests.pick import languages
from tests.test_language_coupling import REFERENCE


def _chosen(name: str) -> DialectSettings:
    """Every setting off its default, where the generator targets that."""
    schema = esolangs.describe(name)["dialect_settings"]
    off = {
        k: next(c for c in i["choices"] if c != i["default"]) for k, i in schema.items()
    }
    try:
        esolangs.generate(name, "01", settings=DialectSettings(**off))
    except esolangs.ArgumentError:
        return DialectSettings(**{k: i["default"] for k, i in schema.items()})
    return DialectSettings(**off)


CASES = [
    (name, _chosen(name))
    for name in languages()
    if esolangs.describe(name)["dialect_settings"]
]


def _invalid() -> list[tuple[str, DialectSettings]]:
    """A choice outside each dialect language's first setting."""
    cases = []
    for name in esolangs.list_languages():
        for key, item in list(esolangs.describe(name)["dialect_settings"].items())[:1]:
            choice = item["choices"][-1]
            bad = choice + 1 if isinstance(choice, int) else "bogus"
            cases.append((name, DialectSettings(**{key: bad})))
    return cases


class Unreadable(StringIO):
    """Fail if argument validation consumes the source or input."""

    def read(self, *_args, **_kwargs):
        raise AssertionError("read before dialect validation")


@pytest.mark.parametrize(
    ("language", "settings", "options"),
    [
        (REFERENCE, DialectSettings(cell_modulus=256), {}),
        (REFERENCE, DialectSettings(cell_modulus=256), {"isolated": True}),
        *[(name, settings, {}) for name, settings in _invalid()],
    ],
)
def test_invalid_settings_fail_before_reading(language, settings, options):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(
            language, Unreadable(), stdin=Unreadable(), settings=settings, **options
        )
    with pytest.raises(esolangs.ArgumentError):
        make_vm(language, Unreadable(), stdin=Unreadable(), settings=settings)
    with pytest.raises(esolangs.ArgumentError):
        esolangs.generate(language, "01", settings=settings)


def test_settings_are_immutable():
    settings = DialectSettings(cell_modulus=255)
    with pytest.raises(FrozenInstanceError):
        settings._items = ()  # noqa: SLF001 - test frozen storage
    assert DialectSettings().options(REFERENCE) == {}


def test_constructor_refuses_a_bool_integer():
    with pytest.raises(esolangs.ArgumentError):
        DialectSettings(cell_modulus=True)


def test_settings_require_the_public_object():
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.run(
            REFERENCE,
            Unreadable(),
            settings={"integer_conversion": "after_each_letter"},
        )


def test_cli_help_shows_literal_settings_json(capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(["generate", "--help"], capsys)
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert '{"expression_syntax":"postfix"}' in help_text


@pytest.mark.parametrize("key", ["index_base", "eof", "input_framing"])
def test_omission_policies_are_not_public_choices(key):
    with pytest.raises(esolangs.ArgumentError, match="unknown dialect setting"):
        DialectSettings(**{key: "default"})


@pytest.mark.parametrize("balance", [False, True])
def test_raster_scaling_retains_settings(balance):
    raster, other = languages(source_kind="raster", boolean_generator=True)[:2]
    settings = DialectSettings()
    source = esolangs.generate(
        raster, "01", scale=2, balance=balance, settings=settings
    )
    assert source.settings is settings
    assert source.tagged(source.language).settings is settings
    assert source.upscaled(1).settings is settings
    assert source.upscaled(2).settings is settings
    assert Raster.from_png(source.to_png()).settings == settings
    assert source.tagged(other).settings is None


def test_inherited_choices_are_checked_before_input():
    source = _Tagged("+.", "brainfuck", DialectSettings(cell_modulus=255))
    with pytest.raises(esolangs.ArgumentError, match="dialect settings"):
        esolangs.run(REFERENCE, source, stdin=Unreadable())


def test_default_pickle_has_no_retained_choices():
    source = esolangs.generate(REFERENCE, "01")
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings is None
    assert esolangs.run(REFERENCE, restored, stdin="1") == "1"


def test_generation_rejects_untyped_settings():
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.generate(REFERENCE, "01", settings={})


@pytest.mark.medium
def test_every_reported_default_and_choice_is_accepted():
    for language in esolangs.list_languages():
        schema = esolangs.describe(language)["dialect_settings"]
        defaults = {key: item["default"] for key, item in schema.items()}
        DialectSettings(**defaults).options(language)
        for key, item in schema.items():
            values = item["choices"]
            if values is None:
                values = (item["minimum"], None)
            for value in values:
                selected = defaults | {key: value}
                for dependency in item["requires"].get(str(value), ()):
                    selected[dependency] = 8
                DialectSettings(**selected).options(language)
            if item["minimum"] is not None:
                with pytest.raises(esolangs.ArgumentError):
                    DialectSettings(**(defaults | {key: item["minimum"] - 1})).options(
                        language
                    )
