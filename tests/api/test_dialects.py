"""Dialect settings: public surface, provenance, evaluation and per-language rules."""

import inspect
import json
import pickle
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs import settings as settings_api
from esolangs.registry import CATALOG, LANGUAGES
from esolangs.registry._functions import FunctionRef
from esolangs.runtime import _execution
from esolangs.runtime._artifact_source import read_png_artifact
from esolangs.vm import complete_vm, make_vm
from tests.support.cli_support import _failure, call_both
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
    assert one.options() == {"mode": 2}
    assert two.options() == {"mode": "right"}
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
    assert scoped.bind(first).settings(catalog="right").options() == {
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
    from esolangs.cli.args import _settings_arguments, _settings_of

    for value in (2, 3):
        document = '{"cell_modulus":2,"cell_modulus":' + str(value) + "}"
        _, error = _failure(
            [operation.__name__, "--settings", document, REFERENCE, "01"], capsys
        )
        assert "duplicate field" in error
    language = one_where(lambda info: "cell_modulus" in info.dialect_settings)[0]
    assert _settings_of(
        _settings_arguments(
            {"--settings": '{"cell_modulus":255}'}, ["cell_modulus=256"]
        ),
        language=language,
    ) == esolangs.Language(language).settings(cell_modulus=256)


def test_cli_help_shows_literal_settings_json(capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        call_both(["generate", "--help"], capsys)
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    from esolangs.cli.help import _capability_examples

    _template, dialects = _capability_examples()
    assert dialects
    assert dialects in help_text


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_cli_rejects_nonstandard_json_before_applying_set(capsys, constant) -> None:
    language = one_where(lambda info: bool(info.dialect_settings))[0]
    key, option = next(iter(esolangs.describe(language).dialect_settings.items()))
    command = [
        "generate",
        "--settings",
        "{" + json.dumps(key) + ":" + constant + "}",
        "--set",
        f"{key}={option['default']}",
        language,
        "01",
    ]
    out, error = _failure(command, capsys)
    assert not out
    assert f"invalid JSON constant {constant}" in error


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
            restored.source.upscaled(scale),
            raster,
            settings=retained,
            scale=restored.scale * scale,
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


def test_custom_dialect_with_large_integer_choices() -> None:
    from dataclasses import replace

    value = 10**5000
    schema = esolangs.DialectSchema(REFERENCE, {"mode": (1, value)}, {"mode": 1})
    original = LANGUAGES[REFERENCE]
    runtime = replace(
        original.runtime, dialect=lambda **choices: choices, dialect_schema=schema
    )
    catalog = esolangs.Catalog([replace(original, runtime=runtime)])
    bound = catalog.bind(REFERENCE)
    settings = bound.settings(mode=value)
    assert eval(repr(settings), {"Language": catalog.bind}) == settings
    with pytest.raises(esolangs.ArgumentError, match=r"integer with .* bits"):
        schema.validate({"mode": 2})
    artifact = bound.from_source("+.", settings=settings)
    replacement = bound.settings(mode=1)
    for operation in (bound.run, bound.prepare):
        with pytest.raises(
            esolangs.ProgramError, match=r"mode=<integer with \d+ bits>, not 1"
        ):
            operation(artifact, settings=replacement)


def test_dialect_settings_from_another_schema_name_the_catalog() -> None:
    from dataclasses import replace

    original = LANGUAGES[REFERENCE]
    schema = esolangs.DialectSchema(REFERENCE, {"mode": (1, 2)}, {"mode": 1})
    runtime = replace(
        original.runtime, dialect=lambda **choices: choices, dialect_schema=schema
    )
    alternate = esolangs.Catalog([replace(original, runtime=runtime)]).bind(REFERENCE)
    settings = alternate.settings(mode=2)
    with pytest.raises(
        esolangs.ArgumentError, match="different schema from this catalog"
    ):
        esolangs.run(REFERENCE, Unreadable(), stdin=Unreadable(), settings=settings)


def test_dialect_keys_survive_binding_and_round_trips(tmp_path: Path) -> None:
    from dataclasses import replace

    names = (
        "catalog",
        "language",
        "schema",
        "self",
        "scale",
        "rng",
        "K",
        "\N{KELVIN SIGN}",
    )
    schema = esolangs.DialectSchema(
        REFERENCE, dict.fromkeys(names, (1, 2)), dict.fromkeys(names, 1)
    )
    original = LANGUAGES[REFERENCE]
    validations = []
    once = False

    def validate(**choices):
        if once and validations:
            raise esolangs.ProgramError("dialect already validated")
        validations.append(choices)
        return choices

    runtime = replace(original.runtime, dialect=validate, dialect_schema=schema)
    bound = CATALOG.with_language(replace(original, runtime=runtime)).bind(REFERENCE)
    choices = dict.fromkeys(names, 2)
    settings = bound.settings(**choices)
    assert settings.options() == choices
    assert DialectSettings(schema, **choices) == settings
    with pytest.raises(TypeError, match="schema"):
        DialectSettings(schema=schema, self=2)
    assert eval(repr(settings), {"Language": bound.catalog.bind}) == settings
    artifact = bound.from_source("+.", settings=settings)
    document = bound.to_json(artifact)
    path = tmp_path / "program"
    path.write_text("+.", encoding="utf-8")

    class CheckedPath:
        calls = 0

        def __fspath__(self) -> str:
            assert validations == [choices]
            self.calls += 1
            return str(path)

    provider = CheckedPath()
    once = True
    for operation, expected in (
        (lambda: bound.from_source("+.", settings=settings), artifact),
        (lambda: bound.from_file(provider, settings=settings), artifact),
        (lambda: bound.from_json(document), artifact),
        (lambda: bound.to_json("+.", settings=settings), document),
        (lambda: bound.to_file("+.", path, settings=settings), None),
    ):
        validations.clear()
        assert operation() == expected
        assert validations == [choices]
    assert provider.calls == 1
    assert path.read_bytes() == b"+."

    envelope = json.loads(document)
    for payload, message in (
        ({"kind": "gzip", "limits": None, "source": "!"}, "base64"),
        (
            {"kind": "template", "char": "?", "setters": [], "spans": []},
            "input templates",
        ),
    ):
        validations.clear()
        with pytest.raises(esolangs.ProgramError, match=message):
            bound.from_json(json.dumps(envelope | payload))
        assert validations == []

    def untouched(**_choices):
        pytest.fail("validating a declaration must not call its dialect hook")

    raster = one_where(lambda info: info.source_kind == "raster")[0]
    random = one_where(lambda info: info.random)[0]
    for name, option in ((raster, "scale"), (random, "rng")):
        schema = esolangs.DialectSchema(name, {option: (1, 2)}, {option: 2})
        with pytest.raises(ValueError, match=rf"dialect setting {option} conflicts"):
            replace(LANGUAGES[name].runtime, dialect=untouched, dialect_schema=schema)


def test_scoped_runtime_defaults_reach_native_and_prepared_execution() -> None:
    from dataclasses import replace

    name = one_where(lambda info: "rotation" in info.dialect_settings)[0]
    stock = esolangs.Language(name)
    declaration = LANGUAGES[name]
    runtime = declaration.runtime
    schema = esolangs.DialectSchema(
        name, runtime.dialect_schema.choices, {"rotation": "forward"}
    )
    with pytest.raises(ValueError, match="default for rotation"):
        replace(runtime, dialect_schema=schema)

    calls = []
    reject_retained = False
    rejected = esolangs.ArgumentError("retained rotation rejected")

    def validate(*, rotation="forward"):
        calls.append(rotation)
        if reject_retained and rotation == "forward":
            raise rejected
        runtime.dialect(rotation=rotation)

    scoped_runtime = replace(runtime, dialect=validate, dialect_schema=schema)
    scope = CATALOG.with_language(replace(declaration, runtime=scoped_runtime)).bind(
        name
    )
    assert scope.describe().dialect_settings["rotation"]["default"] == "forward"
    source = "+,"
    assert stock.run(source).output == ""
    for settings, output in (
        (None, "\x01"),
        (scope.settings(), "\x01"),
        (scope.settings(rotation="backward"), ""),
    ):
        calls.clear()
        artifact = scope.from_source(source, settings=settings)
        portable = scope.from_json(scope.to_json(artifact))
        assert portable.settings == settings
        if settings is None:
            assert not calls
        assert scope.run(source, settings=settings).output == output
        assert scope.run(portable).output == output
        assert complete_vm(scope.make_vm(portable)) == output
        prepared = scope.prepare(portable)
        assert prepared.artifact.settings == settings
        assert prepared.run().output == complete_vm(prepared.make_vm()) == output
        assert calls
        assert set(calls) == {"forward" if output else "backward"}

    generated = scope.generate("01")
    assert generated.settings.options() == {"rotation": "forward"}
    for bit in (0, 1):
        assert scope.evaluate(generated, (bit,)).answer == str(bit)

    restored = scope.from_json(scope.to_json(generated))
    conflicting = scope.settings(rotation="backward")
    reject_retained = True
    for artifact in (generated, restored):
        calls.clear()
        with pytest.raises(esolangs.ProgramError, match="written with rotation="):
            scope.prepare(artifact, settings=conflicting)
        assert calls == ["backward"]
        calls.clear()
        with pytest.raises(esolangs.ArgumentError) as caught:
            scope.prepare(artifact)
        assert caught.value is rejected
        assert calls == ["forward"]


def test_custom_runtime_defaults_follow_declared_runner_keywords(monkeypatch) -> None:
    from dataclasses import replace

    declaration = LANGUAGES[REFERENCE]
    runtime = declaration.runtime
    module = _execution.interpreter_module(REFERENCE)
    execute = getattr(module, runtime.completion_entrypoint)
    prepare = getattr(module, runtime.machine_preparation)

    def expanded(source, options):
        assert options.keys() <= {"increment", "multiplier"}
        return source * options.get("increment", 1) + "." * options.get("multiplier", 1)

    def custom_prepare(source, options):
        return prepare(expanded(source, options), {})

    def named(source, io, increment=1, *, multiplier=1, **options):
        assert not options
        return execute(
            expanded(source, {"increment": increment, "multiplier": multiplier}), io
        )

    def positional(source, io, increment=1, /, *, multiplier=1):
        return named(source, io, increment, multiplier=multiplier)

    def variadic(*args, multiplier=1, **options):
        return named(*args, multiplier=multiplier, **options)

    def opaque(*args, **options):
        return named(*args, **options)

    monkeypatch.setattr(module, "custom_prepare", custom_prepare, raising=False)
    fields = ("source", "io", "increment", "multiplier", "validation_only")
    schema = esolangs.DialectSchema(
        REFERENCE, dict.fromkeys(fields, (1, 2)), dict.fromkeys(fields, 2)
    )
    for runner, default, multiplier, override in (
        (named, "\x02\x02", 1, "\x02"),
        (positional, "\x01\x01", 1, "\x01"),
        (variadic, "\x01\x01", 1, "\x01"),
        (opaque, "\x01", 2, "\x01\x01"),
    ):
        monkeypatch.setattr(module, "custom_execute", runner, raising=False)
        custom = replace(
            runtime,
            completion_entrypoint="custom_execute",
            machine_preparation="custom_prepare",
            dialect=lambda **choices: choices,
            dialect_schema=schema,
        )
        scope = esolangs.Catalog([replace(declaration, runtime=custom)]).bind(REFERENCE)
        for settings, output in (
            (None, default),
            (scope.settings(), default),
            (scope.settings(multiplier=multiplier), override),
        ):
            artifact = scope.from_source("+", settings=settings)
            portable = scope.from_json(scope.to_json(artifact))
            assert portable.settings == settings
            assert scope.run(portable).output == output
            assert complete_vm(scope.make_vm(portable)) == output
            prepared = scope.prepare(portable)
            assert prepared.run().output == complete_vm(prepared.make_vm()) == output


def test_dialect_schema_reports_invalid_mapping_arguments() -> None:
    from collections.abc import Mapping

    class ReportedType:
        def __init__(self, reported):
            self.reported = reported

        @property
        def __class__(self):
            return self.reported

    schema = esolangs.DialectSchema(REFERENCE, {}, {})
    for invalid in ([], ReportedType(Mapping)):
        with pytest.raises(esolangs.ArgumentError, match="mappings"):
            esolangs.DialectSchema(REFERENCE, invalid, {})
        with pytest.raises(esolangs.ArgumentError, match="mapping"):
            schema.validate(invalid)
    for name in (1, ReportedType(str)):
        with pytest.raises(esolangs.ArgumentError, match="names must be strings"):
            schema.validate({name: "left"})
    with pytest.raises(esolangs.ArgumentError, match="requires a language"):
        esolangs.DialectSchema(ReportedType(str), {}, {})
    with pytest.raises(esolangs.ArgumentError, match="enums must be tuples"):
        esolangs.DialectSchema(REFERENCE, {"mode": ReportedType(tuple)}, {"mode": "a"})
    with pytest.raises(esolangs.ArgumentError, match="require a language schema"):
        DialectSettings(ReportedType(esolangs.DialectSchema))


def test_dialect_schema_freezes_enum_tuple_contents() -> None:
    class EnumTuple(tuple):
        def __iter__(self):
            return iter(("first", "injected"))

    schema = esolangs.DialectSchema(
        REFERENCE, {"mode": EnumTuple(("first", "second"))}, {"mode": "first"}
    )
    assert DialectSettings(schema, mode="second").options() == {"mode": "second"}
    with pytest.raises(esolangs.ArgumentError, match="invalid value"):
        DialectSettings(schema, mode="injected")


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
    bound = esolangs.Language(language)
    choices = settings_api.dialect_choices(language)
    defaults = {k: v["default"] for k, v in choices.items()}
    contrary = bound.settings(**{key: other})
    for selected in (None, bound.settings()):
        artifact = bound.generate("0110", settings=selected)
        assert artifact.settings == bound.settings(**defaults)
        for operation in (bound.run, bound.prepare, bound.to_json):
            with pytest.raises(esolangs.ProgramError, match=f"{key}="):
                operation(artifact, settings=contrary)


def test_balanced_generation_retains_partial_dialect_settings() -> None:
    name = one_where(lambda info: "expression_syntax" in info.dialect_settings)[0]
    language = esolangs.Language(name)
    partial = language.settings(expression_syntax="postfix")
    full = language.settings(expression_syntax="postfix", list_update="in_place")
    artifact = language.generate("0110", balance=True, settings=partial)
    assert artifact == language.generate("0110", balance=True, settings=full)
    assert artifact.settings == full
    for row, expected in enumerate("0110"):
        assert language.evaluate(artifact, [row >> 1, row & 1]).answer == expected


def test_every_reported_default_and_choice_is_accepted(monkeypatch) -> None:
    def forbidden(*_args):
        raise AssertionError("dialect discovery reached")

    monkeypatch.setattr(inspect, "signature", forbidden)
    monkeypatch.setattr(_execution, "interpreter_module", forbidden)
    assert not hasattr(settings_api, "_dialect_keys")
    for language in esolangs.list_languages():
        schema = settings_api.dialect_choices(language)
        defaults = {key: item["default"] for key, item in schema.items()}
        assert esolangs.Language(language).settings(**defaults).options() == defaults
        for key, item in schema.items():
            for value in item["choices"]:
                selected = defaults | {key: value}
                assert (
                    esolangs.Language(language).settings(**selected).options()
                    == selected
                )
            choice = item["choices"][-1]
            invalid = choice + 1 if type(choice) is int else "bogus"
            for value in (None, invalid, True):
                with pytest.raises(esolangs.ArgumentError, match="choices: "):
                    esolangs.Language(language).settings(**{key: value})
