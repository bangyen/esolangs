"""Contracts shared by every registered raster language."""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

import esolangs
import esolangs.runtime._execution as _execution_runtime
from esolangs.operations.source import _check_program, read_png_artifact
from esolangs.raster import Raster, lazy_raster
from esolangs.registry import CATALOG, LANGUAGES, SourceKind
from tests.support.dialect_support import integer_setting
from tests.support.evaluation import _evaluate
from tests.support.reference import REFERENCE

RASTER_LANGUAGES = [
    name
    for name, language in LANGUAGES.items()
    if language.runtime.source_kind is SourceKind.RASTER
]


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_committed_png_computes_every_row(language: str) -> None:
    examples = esolangs.describe(language)["examples"]
    assert len(examples) == 1
    path = Path(str(files("esolangs") / examples[0]))
    assert _evaluate(language, path, inputs=2) == "0001"


def test_raster_type_has_neutral_ownership() -> None:
    assert Raster.__module__ == "esolangs.raster"
    assert esolangs.Raster is Raster


def test_a_raster_needs_pixels_or_a_materializer() -> None:
    """Both paths absent is a programmer error, not an empty image."""
    with pytest.raises(ValueError, match="pixels or a materializer"):
        Raster(None)


def test_a_raster_hashes_by_pixels() -> None:
    """It is usable as a mapping key, hashed on its immutable pixels."""
    first = Raster((((0, 0, 0),),))
    second = Raster((((0, 0, 0),),))
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_a_raster_language_has_no_template_to_instantiate() -> None:
    """Runnable raster records have no template bindings."""
    with pytest.raises(esolangs.TemplateError):
        esolangs.instantiate(
            RASTER_LANGUAGES[0], esolangs.generate(RASTER_LANGUAGES[0], "01"), [0]
        )


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_every_raster_language_generates_shared_source(language: str) -> None:
    program = esolangs.generate(language, "01")
    assert isinstance(program.source, Raster)
    assert program.source.rows
    assert program.source.rows[0]
    assert esolangs.describe(language)["source_kind"] == "raster"
    assert esolangs.run(language, program, stdin="1\n").output == "1"


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
@pytest.mark.parametrize("truth_table", ["0", "1"])
def test_every_raster_generator_rejects_zero_inputs(
    language: str, truth_table: str
) -> None:
    with pytest.raises(esolangs.TruthTableError, match="needs at least one input"):
        esolangs.generate(language, truth_table)


@pytest.mark.slow
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_every_raster_language_runs_its_png(language: str, tmp_path: Path) -> None:
    program = esolangs.generate(language, "01")
    assert isinstance(program.source, Raster)
    path = tmp_path / f"{language.lower()}.png"
    esolangs.save_program(language, program, path)
    assert esolangs.run(language, path, stdin="0\n").output == "0"


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_a_malformed_png_is_a_program_error(language: str, tmp_path: Path) -> None:
    """Corrupt bytes escaped the package as zlib/struct/Index/MemoryError."""
    truncated = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 4
    assert issubclass(esolangs.ProgramError, ValueError)
    with pytest.raises(esolangs.ProgramError):
        Raster.from_png(truncated)
    path = tmp_path / f"bad-{language.lower()}.png"
    path.write_bytes(truncated)
    with pytest.raises(esolangs.ProgramError):
        _check_program(language, path)


def test_raster_detaches_mutable_pixels() -> None:
    pixels = [[[0, 0, 0]]]
    raster = Raster(pixels)
    before = hash(raster)
    pixels[0][0][0] = 255
    assert raster.rows == (((0, 0, 0),),)
    assert hash(raster) == before
    assert Raster.from_png(raster.to_png()) == raster


@pytest.mark.parametrize("channel", [1.5, True, "1", None, -1, 256])
def test_raster_refuses_invalid_channel_types(channel: object) -> None:
    with pytest.raises(ValueError, match="8-bit RGB"):
        Raster((((channel, 0, 0),),))


def test_lazy_raster_freezes_once_on_access() -> None:
    pixels = [[[0, 0, 0]]]
    calls = 0

    def materialize() -> list[list[list[int]]]:
        nonlocal calls
        calls += 1
        return pixels

    raster = lazy_raster(materialize)
    assert calls == 0
    assert raster.rows == (((0, 0, 0),),)
    pixels[0][0][0] = 255
    assert raster.rows == (((0, 0, 0),),)
    assert calls == 1
    assert hash(raster) == hash(Raster((((0, 0, 0),),)))


def test_lazy_raster_does_not_cache_invalid_pixels() -> None:
    pixels = [[[256, 0, 0]]]
    raster = lazy_raster(lambda: pixels)
    with pytest.raises(ValueError, match="8-bit RGB"):
        _ = raster.rows
    pixels[0][0][0] = 0
    assert raster.rows == (((0, 0, 0),),)


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_bounded_raster_run_preserves_explicit_scale(language: str, native_png) -> None:
    from esolangs.debugger import make_debugger
    from esolangs.vm import make_vm

    source = esolangs.generate(language, "01", scale=2)
    assert isinstance(source.source, Raster)
    source = esolangs.Language(language).from_source(
        Raster.from_png(native_png(source))
    )
    assert (
        esolangs.run(language, source, stdin="1\n", scale=2, max_steps=1000).output
        == "1"
    )
    vm = make_vm(language, source, stdin="0\n", scale=2)
    while not vm.halted:
        vm.step()
    assert vm.output == "0"
    debugger = make_debugger(language, source, stdin="1\n", scale=2)
    assert debugger.run(max_steps=1000) == "halted"
    assert debugger.output == "1"
    assert esolangs.describe(language)["state_model"] in {"tape", "stack"}


@pytest.mark.parametrize("channel", [True, 1.0])
def test_palette_validation_does_not_confuse_equal_channel_types(
    channel: object,
) -> None:
    valid = (1, 0, 0)
    with pytest.raises(ValueError, match="RGB"):
        Raster(((valid, (channel, 0, 0)),))


@pytest.mark.parametrize("builder_name", ["make_vm", "make_debugger"])
def test_text_step_builders_refuse_raster_scale(builder_name: str) -> None:
    import esolangs.debugger as debugger

    builder = getattr(debugger, builder_name)
    with pytest.raises(esolangs.ArgumentError, match="only supported for raster"):
        builder(REFERENCE, "+", scale=2)
    with pytest.raises(esolangs.ArgumentError):
        builder(REFERENCE, "+", scale=0)


def test_repeated_tuple_rows_with_mutable_pixels_are_revalidated() -> None:
    pixel = [0, 0, 0]
    row = (pixel,)

    def rows():
        yield row
        pixel[0] = 255
        yield row

    assert Raster(rows()).rows == (((0, 0, 0),), ((255, 0, 0),))


def test_repeated_tuple_rows_do_not_hide_an_invalid_mutation() -> None:
    pixel = [0, 0, 0]
    row = (pixel,)

    def rows():
        yield row
        pixel[0] = True
        yield row

    with pytest.raises(ValueError, match="RGB"):
        Raster(rows())


@pytest.mark.parametrize("rows", [((None,),), 5, None, ((5,),), ()])
def test_raster_refuses_with_a_program_error(rows: object) -> None:
    """A raw TypeError or ValueError escaped ``except EsolangError``."""
    with pytest.raises(esolangs.ProgramError):
        Raster(rows)  # type: ignore[arg-type]


def test_raster_repr_names_its_size() -> None:
    assert repr(Raster(((((1, 2, 3),) * 2),))) == ("Raster(2x1)")


def test_an_oversized_upscale_is_refused_before_rendering() -> None:
    """``scale=99999`` was OOM-killed with no message; generate refuses it now."""
    for language in RASTER_LANGUAGES:
        with pytest.raises(esolangs.ArgumentError, match="pixel limit"):
            esolangs.generate(language, "0110", scale=10**4)


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
@pytest.mark.parametrize("scale", [1, 2])
def test_png_metadata_round_trip_executes(language, scale, native_png) -> None:
    settings = esolangs.Language(language).settings()
    source = esolangs.generate(language, "0110", scale=scale, settings=settings)
    restored = _check_program(language, native_png(source))
    assert restored.source.rows == source.source.rows
    assert restored.language == language
    assert restored.settings == settings
    assert restored.scale == scale
    assert restored.source._payload is None
    assert _evaluate(language, restored, inputs=2) == "0110"
    assert _evaluate(language, restored, inputs=2, isolated=True) == "0110"


def test_plain_png_has_no_source_metadata() -> None:
    source = Raster((((1, 2, 3),),))
    restored = Raster.from_png(source.to_png())
    assert restored == source
    assert not hasattr(restored, "language")
    assert not hasattr(restored, "settings")
    assert not hasattr(restored, "scale")


def test_scaling_composes_retained_factors(native_png) -> None:
    source = esolangs.generate(RASTER_LANGUAGES[0], "01", scale=2)
    decoded = _check_program(source.language, native_png(source))
    enlarged = esolangs.ProgramArtifact(
        decoded.source.upscaled(3),
        decoded.language,
        decoded.settings,
        decoded.scale * 3,
    )
    assert _check_program(source.language, native_png(enlarged)).scale == 6


def test_png_settings_retain_integer_choices(native_png) -> None:
    """Integers travel as hex; a settings tag needs its language (1.0 audit)."""
    key = integer_setting()
    owner, choices = next(
        (n, lang.runtime.dialect_schema.choices[key])
        for n, lang in LANGUAGES.items()
        if key
        in (lang.runtime.dialect_schema.choices if lang.runtime.dialect_schema else {})
    )
    settings = esolangs.Language(owner).settings(**{key: choices[-1]})
    source = esolangs.ProgramArtifact(Raster((((1, 2, 3),),)), owner, settings)
    assert read_png_artifact(owner, native_png(source)).settings == settings
    huge = 1 << 20_000  # Past CPython's decimal rendering cap.
    with pytest.raises(esolangs.ArgumentError, match="integer with 20001 bits"):
        esolangs.Language(owner).settings(**{key: huge})
    forged = esolangs.Language(owner).settings()
    object.__setattr__(forged, "_items", ((key, huge),))
    with pytest.raises(
        esolangs.ArgumentError, match="invalid value for dialect setting"
    ):
        esolangs.ProgramArtifact(Raster((((1, 2, 3),),)), owner, forged)


def test_png_language_tag_refuses_cross_language_execution(native_png) -> None:
    source = esolangs.generate(RASTER_LANGUAGES[0], "01")
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        esolangs.run(RASTER_LANGUAGES[1], native_png(source), max_steps=1000)


def test_tagging_unknown_pixels_preserves_automatic_scale_detection() -> None:
    rows = (((255, 0, 0),) * 4,) * 4
    source = esolangs.ProgramArtifact(Raster(rows), RASTER_LANGUAGES[0])
    assert source.scale is None
    assert source.source._normalized() == (((255, 0, 0),),)


@pytest.mark.parametrize("scale", [0, True, -1])
def test_retained_scale_is_validated(scale) -> None:
    with pytest.raises(esolangs.ArgumentError, match="scale"):
        esolangs.ProgramArtifact(
            Raster((((1, 2, 3),),)), RASTER_LANGUAGES[0], scale=scale
        )


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_explicit_scale_overrides_png_metadata(
    language, monkeypatch, native_png
) -> None:
    module = _execution_runtime.interpreter_module(language)
    assert not hasattr(module, "supports_scale")
    monkeypatch.setattr(module, "supports_scale", False, raising=False)
    source = esolangs.generate(language, "01", scale=2)
    changed = esolangs.ProgramArtifact(Raster(source.source.rows), language, scale=7)
    result = esolangs.run(
        language,
        native_png(changed),
        stdin=esolangs.encode_inputs(language, [1]),
        scale=2,
        max_steps=1000,
    )
    assert esolangs.read_answer(language, result.output) == "1"
    spec = LANGUAGES[language]
    caps = replace(spec.runtime.capabilities, supports_scale=False)
    runtime = replace(spec.runtime, capabilities=caps)
    catalog = CATALOG.with_language(replace(spec, runtime=runtime))
    monkeypatch.setattr(module, "supports_scale", True)
    with pytest.raises(esolangs.ArgumentError, match="scale"):
        esolangs.run(language, changed, scale=2, catalog=catalog)
