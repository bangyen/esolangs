"""Scaling survives PNG round trips, including ambiguous codel grids."""

import json
from base64 import b64encode
from dataclasses import replace
from pathlib import Path

import pytest

import esolangs
import esolangs.runtime._execution as _execution_runtime
from esolangs.exceptions import ArgumentError, ProgramError
from esolangs.operations.source import read_png_artifact
from esolangs.raster import Raster, png
from esolangs.raster.scale import detect_scale, normalize
from esolangs.registry import LANGUAGES
from tests.support.evaluation import _evaluate
from tests.support.pick import languages
from tests.support.reference import REFERENCE

RASTER = languages(source_kind="raster", boolean_generator=True)


@pytest.mark.medium
def test_isolation_preserves_scale_beyond_the_decimal_limit() -> None:
    api = esolangs.Language(RASTER[0])
    source = Raster((((0, 0, 0),),))
    scale = 10**5000
    native = api.execute(source, scale=scale)
    assert isinstance(native.error, ProgramError)
    assert "scale" in str(native.error)
    for limits in (
        esolangs.ExecutionLimits(max_steps=2),
        esolangs.ExecutionLimits(total_timeout=5),
        esolangs.ExecutionLimits(execution_timeout=5),
    ):
        outcome = api.execute(source, limits=limits, scale=scale)
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
    assert esolangs.run(name, enlarged, stdin="1\n", scale=Scale(2)).output == "1"


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
        esolangs.run(REFERENCE, "+.", scale=1)
    with pytest.raises(ArgumentError, match="raster"):
        _evaluate(REFERENCE, "+.", inputs=1, scale=1)
    with pytest.raises(ProgramError, match="uniform"):
        esolangs.run(name, image, scale=2)


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
    api = esolangs.Catalog([replace(original, runtime=runtime)]).bind(name)
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
            {"version": 1, "language": name, "settings": {"level": True}},
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

    module = _execution_runtime.interpreter_module(name)
    run = getattr(module, runtime.completion_entrypoint)

    def scoped_run(program, io, *, level, mode, **options):
        assert (level, mode) == (0, "y")
        return run(program, io, **options)

    monkeypatch.setattr(module, runtime.completion_entrypoint, scoped_run)
    for bit in (0, 1):
        stdin = api.encode_inputs([bit])
        assert api.read_answer(
            api.run(path, stdin=stdin, settings=additions).output
        ) == str(bit)
        assert api.read_answer(
            api.run(generated, stdin=stdin, settings=alternate).output
        ) == str(bit)

    monkeypatch.setattr(png, "Image", None)
    conflicting = api.settings(level=1)
    with pytest.raises(
        esolangs.ProgramError, match="invalid value for dialect setting"
    ):
        api.from_file(invalid, settings=conflicting)
    for load in (
        lambda: api.from_file(path, settings=conflicting),
        lambda: api.prepare(path, settings=conflicting),
        lambda: api.to_json(path, settings=conflicting),
        lambda: api.to_file(path, destination, settings=conflicting),
    ):
        with pytest.raises(esolangs.ProgramError, match="written with level=0, not 1"):
            load()
    with pytest.raises(esolangs.MissingDependencyError):
        api.from_file(path, settings=additions)
    assert destination.read_bytes() == copied


def test_png_retains_settings_for_a_lexical_owner(tmp_path: Path) -> None:
    declaration = LANGUAGES[RASTER[0]]
    owner = replace(declaration, name="Scoped Drawing!", id="")
    decoy = replace(
        declaration, name="Alias Drawing", id="", aliases=("scoped-drawing",)
    )
    catalog = esolangs.Catalog([owner, decoy])
    assert catalog.bind("scoped-drawing").name == decoy.name
    api = catalog.bind(owner.name)
    raster = Raster((((1, 2, 3),),))
    path = tmp_path / "source.png"
    for spelling in (" SCOPED-DRAWING ", " scoped_drawing! "):
        tagged = png.write_metadata(
            raster.to_png(), {"version": 1, "language": spelling, "settings": {}}
        )
        assert (
            png.attach_source_metadata(
                tagged, api.name, api.settings(), None, catalog=catalog
            )
            is tagged
        )
        path.write_bytes(tagged)
        assert api.from_file(path) == api.from_source(raster, settings=api.settings())
    path.write_bytes(
        png.write_metadata(
            raster.to_png(), {"version": 1, "language": "Scoped Drawing?"}
        )
    )
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        api.from_file(path)

    owner = replace(declaration, name="Café drawing!", id="")
    api = esolangs.Catalog([owner]).bind(owner.name)
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
        assert "".join(api.evaluate(saved, [bit]).answer for bit in (0, 1)) == "01"
