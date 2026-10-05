"""Contracts shared by every registered raster language."""

from pathlib import Path

import pytest

import esolangs
from esolangs import _check_program
from esolangs._evaluate import _evaluate
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, SourceKind

RASTER_LANGUAGES = [
    name
    for name, language in LANGUAGES.items()
    if language.source_kind is SourceKind.RASTER
]


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_committed_png_computes_every_row(language: str) -> None:
    examples = esolangs.describe(language)["examples"]
    assert len(examples) == 1
    assert _evaluate(language, Path(examples[0]), inputs=2) == "0001"


def test_raster_type_has_neutral_ownership() -> None:
    assert Raster.__module__ == "esolangs.raster"
    assert esolangs.Raster is Raster


def test_a_raster_needs_pixels_or_a_materializer() -> None:
    """Both paths absent is a programmer error, not an empty image."""
    with pytest.raises(ValueError, match="pixels or a materializer"):
        Raster()


def test_a_raster_hashes_by_pixels() -> None:
    """It is usable as a mapping key, hashed on its immutable pixels."""
    first = Raster((((0, 0, 0),),))
    second = Raster((((0, 0, 0),),))
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_a_raster_language_has_no_template_to_instantiate() -> None:
    """``instantiate`` reaches ``_is_template_for`` first, which must refuse it.

    A raster generator returns a :class:`Raster`, not a template string, so
    the comparison cannot succeed; the refusal has to happen rather than
    leaking the raster into ``template.replace``.
    """
    with pytest.raises(esolangs.TemplateError):
        esolangs.instantiate("Piet", "not a template", [0], truth_table="0110")


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_every_raster_language_generates_shared_source(language: str) -> None:
    program = esolangs.generate(language, "01")
    assert isinstance(program, Raster)
    assert program.rows
    assert program.rows[0]
    assert esolangs.describe(language)["source_kind"] == "raster"
    assert esolangs.run(language, program, "1\n") == "1"


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
    assert isinstance(program, Raster)
    path = tmp_path / f"{language.lower()}.png"
    path.write_bytes(program.to_png())
    assert esolangs.run(language, path, "0\n") == "0"


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_a_malformed_png_is_a_program_error(language: str, tmp_path: Path) -> None:
    """Corrupt bytes escaped the package as zlib/struct/Index/MemoryError.

    A truncated IHDR, a bad IDAT and an oversized dimension each raised a
    bare stdlib error from inside the decoder; all are a bad program.
    """
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
    raster = Raster(pixels)  # type: ignore[arg-type]
    before = hash(raster)
    pixels[0][0][0] = 255
    assert raster.rows == (((0, 0, 0),),)
    assert hash(raster) == before
    assert Raster.from_png(raster.to_png()) == raster


@pytest.mark.parametrize("channel", [1.5, True, "1", None, -1, 256])
def test_raster_refuses_invalid_channel_types(channel: object) -> None:
    with pytest.raises(ValueError, match="8-bit RGB"):
        Raster((((channel, 0, 0),),))  # type: ignore[arg-type]


def test_lazy_raster_freezes_once_on_access() -> None:
    pixels = [[[0, 0, 0]]]
    calls = 0

    def materialize() -> list[list[list[int]]]:
        nonlocal calls
        calls += 1
        return pixels

    raster = Raster(_materialize=materialize)  # type: ignore[arg-type]
    assert calls == 0
    assert raster.rows == (((0, 0, 0),),)
    pixels[0][0][0] = 255
    assert raster.rows == (((0, 0, 0),),)
    assert calls == 1
    assert hash(raster) == hash(Raster((((0, 0, 0),),)))


def test_lazy_raster_does_not_cache_invalid_pixels() -> None:
    pixels = [[[256, 0, 0]]]
    raster = Raster(_materialize=lambda: pixels)  # type: ignore[arg-type,return-value]
    with pytest.raises(ValueError, match="8-bit RGB"):
        _ = raster.rows
    pixels[0][0][0] = 0
    assert raster.rows == (((0, 0, 0),),)


@pytest.mark.medium
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_bounded_raster_run_preserves_explicit_scale(language: str) -> None:
    from esolangs.debugger import make_debugger
    from esolangs.vm import make_vm

    source = esolangs.generate(language, "01", scale=2)
    assert isinstance(source, Raster)
    source = Raster.from_png(source.to_png())
    assert esolangs.run(language, source, "1\n", scale=2, max_steps=1000) == "1"
    vm = make_vm(language, source, "0\n", scale=2)
    while not vm.halted:
        vm.step()
    assert vm.output == "0"
    debugger = make_debugger(language, source, "1\n", scale=2)
    assert debugger.run(max_steps=1000) == "halted"
    assert debugger.output == "1"
    assert esolangs.describe(language)["state_model"] in {"tape", "stack"}


@pytest.mark.parametrize("channel", [True, 1.0])
def test_palette_validation_does_not_confuse_equal_channel_types(
    channel: object,
) -> None:
    valid = (1, 0, 0)
    with pytest.raises(ValueError, match="RGB"):
        Raster(((valid, (channel, 0, 0)),))  # type: ignore[arg-type]


def test_palette_validation_remains_bounded() -> None:
    pixels = tuple((i // 256, i % 256, 0) for i in range(1025))
    assert Raster((pixels,)).rows == (pixels,)


@pytest.mark.parametrize("builder_name", ["make_vm", "make_debugger"])
def test_text_step_builders_refuse_raster_scale(builder_name: str) -> None:
    import esolangs.debugger as debugger

    builder = getattr(debugger, builder_name)
    with pytest.raises(esolangs.ArgumentError, match="only supported for raster"):
        builder("brainfuck", "+", scale=2)
    with pytest.raises(esolangs.ArgumentError):
        builder("brainfuck", "+", scale=0)


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


def test_more_than_a_thousand_distinct_rows_remain_exact() -> None:
    rows = tuple(((i // 256, i % 256, 0),) for i in range(1025))
    assert Raster(rows).rows == rows


def test_adjacent_mutable_pixels_are_frozen_on_each_occurrence() -> None:
    class ChangingPixel(list):
        def __iter__(self):
            self[0] += 1
            return iter((self[0], 0, 0))

    pixel = ChangingPixel([0, 0, 0])
    assert Raster(((pixel, pixel),)).rows == (((1, 0, 0), (2, 0, 0)),)


def test_raster_rejects_a_noniterable_pixel() -> None:
    with pytest.raises(TypeError):
        Raster(((None,),))  # type: ignore[arg-type]


@pytest.mark.parametrize("row_type", [tuple, list])
def test_raster_detaches_mutable_pixels_after_an_immutable_prefix(row_type):
    red, black = (255, 0, 0), (0, 0, 0)
    mutable = [1, 2, 3]
    row = row_type([red, red, black, red, mutable, red, red, black])
    raster = Raster((row,))
    assert raster.rows == ((red, red, black, red, (1, 2, 3), red, red, black),)
    mutable[0] = 255
    assert raster.rows[0][4] == (1, 2, 3)
    assert raster.rows[0][0] is red


def test_raster_preserves_validated_immutable_row_identity() -> None:
    red, black = (255, 0, 0), (0, 0, 0)
    row = (red, red, black, red)
    assert Raster((row, row)).rows[0] is row
