"""Contracts shared by every registered raster language."""

from pathlib import Path

import pytest

import esolangs
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, SourceKind

RASTER_LANGUAGES = [
    name
    for name, language in LANGUAGES.items()
    if language.source_kind is SourceKind.RASTER
]


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
        esolangs.check_program(language, path)
