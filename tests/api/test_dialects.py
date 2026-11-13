"""Dialect settings: public surface, provenance, evaluation and per-language rules."""

import inspect
import pickle
from dataclasses import FrozenInstanceError

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs import settings as settings_api
from esolangs.operations.source import read_png_artifact
from esolangs.registry import CATALOG, LANGUAGES
from esolangs.registry._functions import FunctionRef
from esolangs.runtime import _execution
from esolangs.vm import make_vm
from tests.support.cli_support import call_both
from tests.support.dialect_support import (
    Unreadable,
    foreign_settings,
)
from tests.support.pick import languages, one_where
from tests.support.reference import REFERENCE


def _out_of_range() -> list[tuple[str, str, int | str]]:
    """A choice outside each dialect setting of every language."""
    cases = []
    for name in esolangs.list_languages():
        for key, item in esolangs.describe(name).dialect_settings.items():
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
        forged = esolangs.Language(name).settings()
        object.__setattr__(forged, "_items", ((key, bad),))
        cases.append((name, forged))
    return cases


def test_every_dialect_declares_its_values() -> None:
    """A language's ``dialect`` and ``dialect_schema`` name the same settings."""
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
        assert (
            set(
                language.runtime.dialect_schema.choices
                if language.runtime.dialect_schema
                else {}
            )
            == settings
        ), name
        if settings:
            constructor = inspect.signature(
                _execution.interpreter_module(name)._Machine
            )
            assert language.runtime.dialect_schema.defaults == {
                key: constructor.parameters[key].default for key in settings
            }, name

    # The same option name may have unrelated enums in different languages.
    from dataclasses import replace

    from esolangs._dialect import DialectSchema

    first, second = list(LANGUAGES)[:2]
    entered = []
    declared = {"mode": (1, 2)}
    defaults = {"mode": 1}
    first_schema = DialectSchema(first, declared, defaults)
    declared["mode"] = (3, 4)
    defaults["mode"] = 3
    first_schema.choices["mode"] = (5, 6)
    assert first_schema.choices == {"mode": (1, 2)}
    assert first_schema.defaults == {"mode": 1}
    schemas = (
        first_schema,
        DialectSchema(second, {"mode": ("left", "right")}, {"mode": "left"}),
    )

    def record_mode(mode):
        entered.append(mode)

    catalog = CATALOG
    for schema in schemas:
        original = LANGUAGES[schema.language]
        runtime = replace(
            original.runtime,
            dialect_schema=schema,
            dialect=record_mode,
        )
        catalog = catalog.with_language(replace(original, runtime=runtime))
    one = esolangs.Language(first, catalog=catalog).settings(mode=2)
    two = esolangs.Language(second, catalog=catalog).settings(mode="right")
    assert one.options(first) == {"mode": 2}
    assert two.options(second) == {"mode": "right"}
    assert entered == [2, "right"]
    for language, value in ((first, "right"), (second, 2)):
        with pytest.raises(esolangs.ArgumentError, match="choices:"):
            esolangs.Language(language, catalog=catalog).settings(mode=value)
    with pytest.raises(esolangs.ArgumentError, match="settings belong"):
        esolangs.run(
            first, Unreadable(), stdin=Unreadable(), settings=two, catalog=catalog
        )
    with pytest.raises(esolangs.ArgumentError, match="settings belong"):
        esolangs.generate(second, "01", settings=one, catalog=catalog)
    named = DialectSchema(first, {"catalog": ("left", "right")}, {"catalog": "left"})
    declaration = LANGUAGES[first]
    scoped = CATALOG.with_language(
        replace(
            declaration,
            runtime=replace(
                declaration.runtime,
                dialect_schema=named,
                dialect=lambda catalog: catalog,
            ),
        )
    )
    assert scoped.bind(first).settings(catalog="right").options(first) == {
        "catalog": "right"
    }
    assert CATALOG.languages[first] is declaration


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
        {"--settings": '{"cell_modulus":255}'},
        ["cell_modulus=256"],
        language=one_where(lambda info: "cell_modulus" in info.dialect_settings)[0],
    ) == esolangs.Language(
        one_where(lambda info: "cell_modulus" in info.dialect_settings)[0]
    ).settings(cell_modulus=256)


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
    # Brainfuck has no settings; the message ended "known settings: ".
    with pytest.raises(esolangs.ArgumentError, match=r"setting.*it has none$"):
        esolangs.Language("brainfuck").settings(**{key: "default"})


@pytest.mark.parametrize("balance", [False, True])
def test_raster_scaling_retains_settings(balance, native_png) -> None:
    raster, other = languages(source_kind="raster", boolean_generator=True)[:2]
    settings = esolangs.Language(raster).settings()
    source = esolangs.generate(
        raster, "01", scale=2, balance=balance, settings=settings
    )
    assert source.settings is settings
    restored = read_png_artifact(raster, native_png(source))
    assert restored.settings == settings
    retained = restored.settings
    for scale in (1, 2):
        changed = esolangs.ProgramArtifact(
            restored.source.upscaled(scale), raster, retained, restored.scale * scale
        )
        assert changed.settings is retained
    reassigned = esolangs.ProgramArtifact(restored.source, other)
    assert reassigned.settings is None
    assert not hasattr(restored.source, "settings")


def test_inherited_choices_are_checked_before_input() -> None:
    source = esolangs.ProgramArtifact("+.", REFERENCE)
    object.__setattr__(source, "settings", foreign_settings())
    with pytest.raises(esolangs.ArgumentError, match="dialect settings"):
        esolangs.run(REFERENCE, source, stdin=Unreadable())


@pytest.mark.parametrize(
    "settings",
    [
        esolangs.Language("brainfuck").settings(),
        esolangs.Language(
            one_where(lambda info: "expression_syntax" in info.dialect_settings)[0]
        ).settings(expression_syntax="postfix"),
    ],
)
def test_settings_are_immutable_and_repr_rebuilds_them(
    settings: DialectSettings,
) -> None:
    """It printed ``DialectSettings(_items=(...))``, a private field."""
    assert eval(repr(settings), {"Language": esolangs.Language}) == settings
    with pytest.raises(FrozenInstanceError):
        settings._items = ()


def test_default_pickle_has_no_retained_choices() -> None:
    source = esolangs.generate(REFERENCE, "01")
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings is None
    assert esolangs.run(REFERENCE, restored, stdin="1").output == "1"


def _contradicted() -> list[tuple[str, str, int | str]]:
    """Each generator's first dialect setting with a non-default choice."""
    cases = []
    for name in esolangs.list_languages():
        info = esolangs.describe(name)
        if not info.boolean_generator or not info.dialect_settings:
            continue
        key, item = next(iter(info.dialect_settings.items()))
        other = next(value for value in item["choices"] if value != item["default"])
        cases.append((name, key, other))
    return cases


@pytest.mark.parametrize(("language", "key", "other"), _contradicted())
def test_generated_programs_refuse_a_contradicting_dialect(
    language: str, key: str, other: int | str
) -> None:
    """An infix Alight program run as postfix misparsed instead of refusing."""
    artifact = esolangs.generate(language, "0110")
    choices = settings_api.dialect_choices(language)
    defaults = {k: v["default"] for k, v in choices.items()}
    assert artifact.settings == esolangs.Language(language).settings(**defaults)
    contrary = esolangs.Language(language).settings(**{key: other})
    for operation in (
        lambda: esolangs.run(language, artifact, settings=contrary),
        lambda: esolangs.Language(language).prepare(artifact, settings=contrary),
        lambda: esolangs.dump_program(language, artifact, settings=contrary),
    ):
        with pytest.raises(esolangs.ProgramError, match=f"{key}="):
            operation()


def test_every_reported_default_and_choice_is_accepted(monkeypatch) -> None:
    def forbidden(*_args):
        raise AssertionError("dialect discovery reached")

    monkeypatch.setattr(inspect, "signature", forbidden)
    monkeypatch.setattr(_execution, "interpreter_module", forbidden)
    assert not hasattr(settings_api, "_dialect_keys")
    for language in esolangs.list_languages():
        schema = settings_api.dialect_choices(language)
        defaults = {key: item["default"] for key, item in schema.items()}
        assert (
            esolangs.Language(language).settings(**defaults).options(language)
            == defaults
        )
        for key, item in schema.items():
            for value in item["choices"]:
                selected = defaults | {key: value}
                assert (
                    esolangs.Language(language).settings(**selected).options(language)
                    == selected
                )
            choice = item["choices"][-1]
            invalid = choice + 1 if type(choice) is int else "bogus"
            for value in (None, invalid, True):
                with pytest.raises(esolangs.ArgumentError, match="choices: "):
                    esolangs.Language(language).settings(**{key: value})
