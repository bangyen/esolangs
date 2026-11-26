"""Scaling survives PNG round trips, including ambiguous codel grids."""

import json
from base64 import b64encode
from dataclasses import replace
from enum import IntEnum
from pathlib import Path

import pytest

import esolangs
import esolangs.runtime._execution as _execution_runtime
from esolangs.exceptions import ArgumentError, ProgramError
from esolangs.raster import Raster, _png_chunks, png
from esolangs.raster.scale import detect_scale, normalize
from esolangs.registry import LANGUAGES, Catalog
from esolangs.runtime._artifact_source import read_png_artifact
from tests.support.evaluation import _evaluate
from tests.support.pick import languages
from tests.support.reference import REFERENCE

RASTER = languages(source_kind="raster", boolean_generator=True)


@pytest.mark.parametrize("arity", [None, False, True, 0, -1, 1.0, "1"])
def test_bad_native_arity_is_refused_before_decoding(arity, monkeypatch) -> None:
    language = RASTER[0]
    api = esolangs.Language(language)
    raster = esolangs.Raster((((1, 2, 3),),))
    document = json.loads(api.to_json(raster))
    tagged = png.write_metadata(
        raster.to_png(),
        {
            "version": 1,
            "language": language,
            "settings": None,
            "scale": None,
            "input_arity": arity,
        },
    )
    document["source"] = b64encode(tagged).decode("ascii")
    monkeypatch.setattr(png, "Image", None)
    for load in (
        lambda: read_png_artifact(language, tagged),
        lambda: api.from_json(json.dumps(document)),
    ):
        with pytest.raises(
            esolangs.ProgramError, match="input_arity must be a positive integer"
        ):
            load()


def test_source_png_requires_all_metadata_fields_when_tagged() -> None:
    api = esolangs.Language(RASTER[0])
    raster = esolangs.Raster((((1, 2, 3),),))
    data = raster.to_png()
    assert read_png_artifact(api.name, data).source == raster
    document = json.loads(api.to_json(raster))
    complete = {"version": 1, "language": api.name, "settings": None, "scale": None}
    for field in ("language", "settings", "scale"):
        tagged = png.write_metadata(
            data, {key: value for key, value in complete.items() if key != field}
        )
        document["source"] = b64encode(tagged).decode("ascii")
        for load in (
            lambda tagged=tagged: read_png_artifact(api.name, tagged),
            lambda: api.from_json(json.dumps(document)),
            lambda tagged=tagged: png.attach_source_metadata(tagged, api.name, None, 1),
        ):
            with pytest.raises(
                esolangs.ProgramError, match="requires language, settings and scale"
            ):
                load()


@pytest.mark.medium
def test_isolation_preserves_scale_beyond_the_decimal_limit() -> None:
    api = esolangs.Language(RASTER[0])
    source = Raster((((0, 0, 0),),))
    scale = 10**5000
    native = api.run(source, scale=scale)
    assert isinstance(native.error, ProgramError)
    assert "scale" in str(native.error)
    for limits in (
        esolangs.ExecutionLimits(max_steps=2),
        esolangs.ExecutionLimits(total_timeout=5),
        esolangs.ExecutionLimits(execution_timeout=5),
    ):
        outcome = api.run(source, limits=limits, scale=scale)
        assert type(outcome.error) is type(native.error)
        assert str(outcome.error) == str(native.error)
        assert outcome.observation == native.observation


@pytest.mark.medium
@pytest.mark.parametrize("name", RASTER)
@pytest.mark.parametrize("balanced", [False, True])
@pytest.mark.parametrize("scale", [2, 3])
def test_scaled_png_computes_every_row(
    name: str, scale: int, native_png, *, balanced: bool
) -> None:
    native = esolangs.generate(name, "0001", balance=balanced)
    enlarged = esolangs.generate(name, "0001", balance=balanced, scale=scale)
    assert isinstance(native.source, Raster)
    assert isinstance(enlarged.source, Raster)
    assert len(enlarged.source.rows) == len(native.source.rows) * scale
    assert len(enlarged.source.rows[0]) == len(native.source.rows[0]) * scale
    decoded = esolangs.Language(name).from_source(Raster.from_png(native_png(enlarged)))
    assert _evaluate(name, decoded, inputs=2, scale=scale) == "0001"
    assert _evaluate(name, decoded, inputs=2, scale=scale, isolated=True) == "0001"


def test_generic_detection_finds_a_large_scale(native_png) -> None:
    image = esolangs.generate(RASTER[-1], "0001", scale=17)
    assert detect_scale(Raster.from_png(native_png(image)).rows) == 17


@pytest.mark.parametrize("name", RASTER)
def test_scale_subclass_cannot_change_geometric_or_metadata_semantics(
    name: str,
) -> None:
    class Scale(int):
        __hash__ = None

        def __eq__(self, _other):
            return True

        def __int__(self):
            return 1

    base = esolangs.generate(name, "01")
    enlarged = esolangs.generate(name, "01", scale=Scale(2))
    assert isinstance(base.source, Raster)
    assert isinstance(enlarged.source, Raster)
    assert enlarged.source == base.source.upscaled(2)
    assert type(enlarged.scale) is int
    assert enlarged.scale == 2
    record = esolangs.ProgramArtifact(enlarged.source, name, scale=Scale(2))
    assert type(record.scale) is int
    assert hash(record) == hash(
        esolangs.ProgramArtifact(enlarged.source, name, scale=2)
    )
    assert (
        esolangs.run(name, enlarged, stdin="1\n", scale=Scale(2)).unwrap().output == "1"
    )

    class Arity(IntEnum):
        ONE = 1

    api = esolangs.Language(name)
    typed = replace(base, input_arity=Arity.ONE)
    assert type(typed.input_arity) is int
    assert api.from_json(api.to_json(typed)) == base
    data = png.attach_source_metadata(
        base.source.to_png(), api.name, None, base.scale, input_arity=Arity.ONE
    )
    native = read_png_artifact(api.name, data)
    assert native == base
    assert native.evaluate([1]).answer == "1"


@pytest.mark.parametrize("name", RASTER)
def test_scale_validation_and_uniformity(name: str) -> None:
    image = Raster((((0, 0, 0), (255, 255, 255)), ((0, 0, 0), (0, 0, 0))))
    assert image.upscaled(1) is image
    assert normalize(image.rows) is image.rows
    assert not hasattr(image.upscaled(2), "language")
    with pytest.raises(ProgramError, match="uniform"):
        normalize(image.rows, 2)
    with pytest.raises(ProgramError, match="divisible"):
        normalize(image.rows, 3)
    for scale in (True, 0, -1, 1.5, "2", None):
        with pytest.raises(ArgumentError, match="scale"):
            image.upscaled(scale)
        if scale is not None:
            with pytest.raises(ArgumentError, match="scale"):
                esolangs.generate(name, "00", scale=scale)
    with pytest.raises(ArgumentError, match="raster"):
        esolangs.generate(REFERENCE, "00", scale=2)
    with pytest.raises(ArgumentError, match="raster"):
        esolangs.run(REFERENCE, "+.", scale=1).unwrap()
    with pytest.raises(ArgumentError, match="raster"):
        _evaluate(REFERENCE, "+.", inputs=1, scale=1)
    with pytest.raises(ProgramError, match="uniform"):
        esolangs.run(name, image, scale=2).unwrap()


def test_monochrome_codel_grid() -> None:
    image = Raster((((255, 0, 0),) * 6,) * 4)
    assert detect_scale(image.rows) == 2
    assert len(normalize(image.rows)) == 2


@pytest.mark.parametrize("value", ["x", "0", "-1", "1.5"])
def test_cli_rejects_invalid_scale(value, monkeypatch, capsys) -> None:
    import sys

    from esolangs.cli import main

    argv = ["esolangs", "generate", "--scale", value, RASTER[0], "00"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "--scale must be a positive integer" in capsys.readouterr().err


def test_native_png_checks_explicit_settings_before_pillow(
    tmp_path, monkeypatch
) -> None:
    name = RASTER[0]
    original = LANGUAGES[name]
    schema = esolangs.DialectSchema(
        name,
        {"level": (0, 1), "mode": ("x", "y")},
        {"level": 0, "mode": "x"},
    )
    validations = []
    once = False

    def validate(**choices):
        if once and validations:
            raise esolangs.ProgramError("dialect already validated")
        validations.append(choices)

    runtime = replace(original.runtime, dialect=validate, dialect_schema=schema)
    api = Catalog([replace(original, runtime=runtime)]).bind(name)
    generated = esolangs.generate(name, "01", scale=2)
    source = replace(generated, settings=api.settings(level=0))
    path = tmp_path / "source.png"
    destination = tmp_path / "destination.png"
    api.to_file(source, path)
    additions = api.settings(mode="y")
    validations.clear()
    retained = api.from_file(path, settings=additions)
    assert validations == [{"mode": "y"}, {"level": 0}, {"mode": "y", "level": 0}]
    assert retained == replace(source, settings=api.settings(level=0, mode="y"))
    assert api.from_json(api.to_json(path, settings=additions)) == retained
    api.to_file(path, destination, settings=additions)
    assert api.from_file(destination) == retained
    copied = destination.read_bytes()

    class AlternateSettings(esolangs.DialectSettings):
        @property
        def language(self) -> str:
            return "Different Scope"

        def options(self):
            return {"level": 1, "mode": "x"}

    alternate = AlternateSettings(schema, level=0, mode="y")
    assert replace(generated, settings=alternate) == retained
    assert api.from_json(api.to_json(generated, settings=alternate)) == retained
    assert (
        png.write_source(
            generated.source.rows,
            name,
            alternate,
            2,
            input_arity=1,
            catalog=api.catalog,
        )
        == copied
    )
    document = api.to_json(retained)
    same = api.settings(level=0, mode="y")
    assert same is not retained.settings
    pixels = generated.source.to_png()
    bare = api.from_source(generated.source, settings=same)
    copy = tmp_path / "matching.png"
    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(
        png.write_metadata(
            pixels,
            {
                "version": 1,
                "language": name,
                "settings": {"level": True},
                "scale": None,
            },
        )
    )
    once = True
    for supplied in (retained.settings, same, alternate):
        for operation, expected in (
            (lambda choices: api.from_file(destination, settings=choices), retained),
            (lambda choices: api.to_json(retained, settings=choices), document),
            (lambda choices: api.to_file(destination, copy, settings=choices), None),
        ):
            validations.clear()
            assert operation(supplied) == expected
            assert validations == [{"level": 0, "mode": "y"}]
    for data, expected in ((copied, retained), (pixels, bare)):
        validations.clear()
        assert (
            read_png_artifact(name, data, settings=same, catalog=api.catalog)
            == expected
        )
        assert validations == [{"level": 0, "mode": "y"}]
    assert copy.read_bytes() == copied
    once = False

    for arity, message in (
        (False, "stored PNG input_arity must be a positive integer"),
        (2, "conflicting PNG input_arity"),
    ):
        tagged = png.write_metadata(
            pixels,
            {
                "version": 1,
                "language": name,
                "settings": {"level": {"integer": "0x0"}},
                "scale": None,
                "input_arity": arity,
            },
        )
        validations.clear()
        with pytest.raises(esolangs.ProgramError, match=message):
            png.attach_source_metadata(
                tagged, name, None, 2, input_arity=1, catalog=api.catalog
            )
        assert validations == []

    module = _execution_runtime.interpreter_module(name)
    run = getattr(module, runtime.completion_entrypoint)

    def scoped_run(program, io, *, level, mode, **options):
        assert (level, mode) == (0, "y")
        return run(program, io, **options)

    monkeypatch.setattr(module, runtime.completion_entrypoint, scoped_run)
    for bit in (0, 1):
        stdin = api.encode_inputs([bit])
        assert api.read_answer(
            api.run(path, stdin=stdin, settings=additions).unwrap().output
        ) == str(bit)
        assert api.read_answer(
            api.run(generated, stdin=stdin, settings=alternate).unwrap().output
        ) == str(bit)

    monkeypatch.setattr(png, "Image", None)
    conflicting = api.settings(level=1)
    with pytest.raises(
        esolangs.ProgramError, match="invalid value for dialect setting"
    ):
        api.from_file(invalid, settings=conflicting)
    once = True
    for load in (
        lambda: api.from_file(path, settings=conflicting),
        lambda: api.prepare(path, settings=conflicting),
        lambda: api.to_json(path, settings=conflicting),
        lambda: api.to_file(path, destination, settings=conflicting),
    ):
        validations.clear()
        with pytest.raises(esolangs.ProgramError, match="written with level=0, not 1"):
            load()
        assert validations == [{"level": 1}]
    once = False
    with pytest.raises(esolangs.MissingDependencyError):
        api.from_file(path, settings=additions)
    assert destination.read_bytes() == copied


def test_png_retains_settings_for_a_lexical_owner(tmp_path: Path) -> None:
    declaration = LANGUAGES[RASTER[0]]
    owner = replace(declaration, name="Scoped Drawing!", id="")
    decoy = replace(
        declaration, name="Alias Drawing", id="", aliases=("scoped-drawing",)
    )
    catalog = Catalog([owner, decoy])
    assert catalog.bind("scoped-drawing").name == decoy.name
    api = catalog.bind(owner.name)
    raster = Raster((((1, 2, 3),),))
    path = tmp_path / "source.png"
    for spelling in (" SCOPED-DRAWING! ", " scoped_drawing! "):
        tagged = png.write_metadata(
            raster.to_png(),
            {"version": 1, "language": spelling, "settings": {}, "scale": None},
        )
        assert (
            png.attach_source_metadata(
                tagged, api.name, api.settings(), None, catalog=catalog
            )
            is tagged
        )
        path.write_bytes(tagged)
        assert api.from_file(path) == api.from_source(raster, settings=api.settings())
    for spelling in (" SCOPED-DRAWING ", "Scoped Drawing?"):
        path.write_bytes(
            png.write_metadata(
                raster.to_png(),
                {"version": 1, "language": spelling, "settings": None, "scale": None},
            )
        )
        with pytest.raises(esolangs.ProgramError, match="generated for"):
            api.from_file(path)

    owner = replace(declaration, name="Café drawing!", id="")
    api = Catalog([owner]).bind(owner.name)
    settings = api.settings()
    record = api.generate("01", settings=settings, scale=2)
    api.to_file(record, path)
    native = path.read_bytes()
    raw = record.source.to_png()
    alias = "Cafe\u0301 drawing!"
    assert (
        png.write_source(record.source.rows, alias, settings, 2, input_arity=1)
        == native
    )
    assert png.attach_source_metadata(raw, alias, settings, 2, input_arity=1) == native
    tag = png.read_metadata(native) | {"language": alias}
    altered = png.write_metadata(raw, tag)
    assert png.attach_source_metadata(altered, owner.name, None, 2) is altered
    assert png.attach_source_metadata(altered, alias, settings, 2) is altered
    with pytest.raises(esolangs.ProgramError, match="conflicting PNG language"):
        png.attach_source_metadata(altered, "cafe_drawing", None, 2)
    path.write_bytes(altered)
    native_record = api.from_file(path)
    portable = json.loads(api.to_json(record))
    portable["language"] = alias
    portable["source"] = b64encode(altered).decode("ascii")
    rematerialized = api.from_json(json.dumps(portable))
    assert native_record == rematerialized == record
    for saved in (native_record, rematerialized):
        assert "".join(saved.evaluate([bit]).answer for bit in (0, 1)) == "01"

    owner = replace(declaration, name="Color\x1b[2J\nMachine", id="")
    decoy = replace(declaration, name="Other\x1b[2J\nMachine", id="")
    api = Catalog([owner, decoy]).bind(owner.name)
    label = r"Color\x1b[2J\nMachine"
    settings = api.settings()
    record = api.generate("01", settings=settings, scale=2)
    raw = record.source.to_png()
    api.to_file(record, path)
    native = path.read_bytes()
    for restored in (api.from_file(path), api.from_json(api.to_json(record))):
        assert restored == record
        assert "".join(restored.evaluate([bit]).answer for bit in (0, 1)) == "01"
    malformed = png.write_metadata(
        raw, png.read_metadata(native) | {"settings": {"mode": "enabled"}}
    )
    path.write_bytes(malformed)
    with pytest.raises(esolangs.ProgramError) as invalid:
        api.from_file(path)
    assert f"unknown dialect setting for {label}: mode" in str(invalid.value)
    with pytest.raises(esolangs.ProgramError) as refused:
        png.attach_source_metadata(malformed, None, None, 2, catalog=api.catalog)
    expected = f"cannot tag PNG: {label} declares no PNG dialect settings"
    assert str(refused.value) == expected
    with pytest.raises(esolangs.ArgumentError) as foreign:
        png.attach_source_metadata(raw, decoy.name, settings, 2, catalog=api.catalog)
    assert str(foreign.value) == (
        f"dialect settings belong to {label}, " r"not Other\x1b[2J\nMachine"
    )


def test_critical_chunks_are_unique_and_ordered() -> None:
    from tests.runtime.raster.test_png import _chunk

    image = png.write_grey([bytearray([0])])
    header, payload, trailer = [_chunk(k, b) for k, b in _png_chunks._chunks(image)]
    auxiliary = _chunk(b"aUNG", b"")
    empty_idat = _chunk(b"IDAT", b"")
    cases = (
        ((auxiliary, header, payload, trailer), "IHDR must appear first"),
        ((header, header, payload, trailer), "IHDR must appear first"),
        ((header, trailer), "no IDAT"),
        ((header, payload, auxiliary, empty_idat, trailer), "IDAT.*consecutive"),
        ((header, payload, _chunk(b"AUNG", b""), trailer), "critical chunk AUNG"),
    )
    for chunks, message in cases:
        with pytest.raises(esolangs.ProgramError, match=message):
            esolangs.Raster.from_png(_png_chunks._SIGNATURE + b"".join(chunks))
    control = b"\x1b[2J"
    chunk = _chunk(control, b"x")
    for invalid, message in (
        (chunk, r"unknown PNG critical chunk \x1b[2J"),
        (chunk[:8], r"truncated \x1b[2J chunk"),
        (chunk[:-4], r"truncated \x1b[2J chunk CRC"),
        (chunk[:-4] + bytes(4), r"invalid \x1b[2J chunk CRC"),
    ):
        with pytest.raises(esolangs.ProgramError) as failure:
            esolangs.Raster.from_png(
                _png_chunks._SIGNATURE + header + payload + invalid
            )
        assert str(failure.value) == f"not a readable PNG: {message}"
    assert esolangs.Raster.from_png(
        _png_chunks._SIGNATURE + header + empty_idat + payload + auxiliary + trailer
    ) == esolangs.Raster.from_png(image)


def test_scoped_settings_hook_preserves_deliberate_failures(tmp_path: Path) -> None:
    installed = esolangs.Language(RASTER[0])
    name = installed.name
    declaration = installed.catalog.languages[name]
    schema = esolangs.DialectSchema(name, {"mode": (0, 1)}, {"mode": 0})
    failures: list[Exception] = []
    validations = []

    def validate(**choices):
        validations.append(choices)
        if failures:
            raise failures[-1]
        return choices

    runtime = replace(declaration.runtime, dialect=validate, dialect_schema=schema)
    scoped = Catalog([replace(declaration, runtime=runtime)]).bind(name)
    settings = scoped.settings()
    artifact = replace(installed.generate("01", scale=2), settings=settings)
    raw = artifact.source.to_png()
    writers = (
        lambda: png.write_source(
            artifact.source.rows, name, settings, 2, catalog=scoped.catalog
        ),
        lambda: png.attach_source_metadata(
            raw, name, settings, 2, catalog=scoped.catalog
        ),
    )
    for write in writers:
        validations.clear()
        write()
        assert validations == [{}]
    encoded = png.write_metadata(
        raw,
        {
            "version": 1,
            "language": name,
            "settings": {"mode": {"integer": "0x1"}},
            "scale": None,
        },
    )
    matching = scoped.settings(mode=1)
    validations.clear()
    assert (
        png.attach_source_metadata(
            encoded, name, matching, None, catalog=scoped.catalog
        )
        is encoded
    )
    assert validations == [{"mode": 1}]
    with pytest.raises(esolangs.ProgramError, match="conflicting PNG settings"):
        png.attach_source_metadata(
            encoded, name, scoped.settings(mode=0), None, catalog=scoped.catalog
        )

    retained = png.write_metadata(
        raw, {"version": 1, "language": name, "scale": 2, "settings": {}}
    )

    def retag():
        return png.attach_source_metadata(
            retained, name, None, 2, input_arity=1, catalog=scoped.catalog
        )

    validations.clear()
    tagged = retag()
    assert validations == [{}]
    assert tagged == png.attach_source_metadata(retained, name, None, 2, input_arity=1)
    assert validations == [{}]
    path = tmp_path / "program.png"
    path.write_bytes(tagged)
    restored = scoped.from_file(path)
    assert restored == artifact
    assert "".join(restored.evaluate([bit]).answer for bit in (0, 1)) == "01"

    scoped.to_file(artifact, path)
    portable = scoped.to_json(artifact)
    for load in (lambda: scoped.from_file(path), lambda: scoped.from_json(portable)):
        validations.clear()
        assert load() == artifact
        assert validations == [{}]
    prepared = scoped.prepare(path)
    assert prepared.run(stdin="1").unwrap().output == "1"

    nested = esolangs.Language(REFERENCE).run(
        "+.[+]", limits=esolangs.ExecutionLimits(max_steps=2)
    )
    assert nested.observation.output == "\x01"
    timeout = esolangs.ExecutionTimeoutError("dialect hook timed out")
    timeout.bound = "preparation_timeout"
    errors = (
        esolangs.ProgramNotFoundError("policy not found"),
        esolangs.ProgramError("policy failed"),
        esolangs.ArgumentError("policy refused"),
        timeout,
    )
    for error in errors:
        error.observation = nested.observation
        error.partial_output = nested.observation.output
        failures[:] = [error]
        for load in (
            lambda: scoped.from_file(path),
            lambda: scoped.prepare(path),
            lambda: scoped.from_json(portable),
            lambda: scoped.from_source(artifact.source, settings=settings),
            *writers,
            retag,
        ):
            with pytest.raises(type(error)) as caught:
                load()
            assert caught.value is error
        for outcome in (
            scoped.run(path),
            scoped.run(artifact),
            scoped.run(artifact.source, settings=settings),
        ):
            assert outcome.error is error
            assert outcome.status == ("limit" if error is timeout else "rejected")
            assert outcome.bound == (timeout.bound if error is timeout else None)
            assert outcome.observation == esolangs.ExecutionResult("", None, None, None)
        assert error.observation is nested.observation
        assert error.partial_output == "\x01"

    failures[:] = [errors[2]]
    document = json.loads(portable)
    native = path.read_bytes()
    document["source"] = b64encode(native).decode("ascii")
    claims = png.read_metadata(native)
    malformed = tmp_path / "malformed.png"
    for changes, message in (
        ({"language": "Foreign raster"}, "generated for Foreign raster"),
        ({"input_arity": False}, "input_arity must be a positive integer"),
        ({"scale": 0}, "scale must be a positive integer"),
        ({"settings": {"mode": False}}, "invalid value for dialect setting"),
        ({"settings": {"mode": 1}}, "integer settings need a hexadecimal string"),
    ):
        data = png.write_metadata(raw, claims | changes)
        malformed.write_bytes(data)
        encoded = b64encode(data).decode("ascii")
        for load in (
            lambda: scoped.from_file(malformed),
            lambda encoded=encoded: scoped.from_json(
                json.dumps(document | {"source": encoded})
            ),
        ):
            validations.clear()
            with pytest.raises(esolangs.ProgramError, match=message):
                load()
            assert validations == []
    for changes, message in (
        ({"input_arity": False}, "input_arity must be a positive integer"),
        ({"input_arity": 2}, "conflicting PNG and document input_arity"),
        ({"scale": 3}, "conflicting PNG and document scale"),
        ({"settings": {"mode": 1}}, "integer settings need a hexadecimal string"),
        (
            {"settings": {"mode": {"integer": "0x1"}}},
            "conflicting PNG and document settings",
        ),
        ({"kind": "unknown"}, "unknown source kind"),
    ):
        validations.clear()
        with pytest.raises(esolangs.ProgramError, match=message):
            scoped.from_json(json.dumps(document | changes))
        assert validations == []

    failures[:] = [TypeError("ordinary validation failure")]
    for load in (
        lambda: scoped.from_file(path),
        lambda: scoped.from_json(portable),
        retag,
    ):
        with pytest.raises(esolangs.ProgramError, match="invalid dialect settings"):
            load()
    assert prepared.run(stdin="0").unwrap().output == "0"
