"""Contracts shared by every registered raster language."""

from pathlib import Path

import pytest

import esolangs
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES, SourceKind

RASTER_LANGUAGES = [
    name for name, language in LANGUAGES.items() if language.source_kind is SourceKind.RASTER
]


def test_raster_type_has_neutral_ownership() -> None:
    assert Raster.__module__ == "esolangs.raster"
    assert esolangs.Raster is Raster


@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_every_raster_language_generates_shared_source(language: str) -> None:
    program = esolangs.generate(language, "01")
    assert isinstance(program, Raster)
    assert program.rows and program.rows[0]
    assert esolangs.describe(language)["source_kind"] == "raster"
    assert esolangs.run(language, program, "1\n") == "1"


@pytest.mark.slow
@pytest.mark.parametrize("language", RASTER_LANGUAGES)
def test_every_raster_language_runs_its_png(language: str, tmp_path: Path) -> None:
    program = esolangs.generate(language, "01")
    assert isinstance(program, Raster)
    path = tmp_path / f"{language.lower()}.png"
    path.write_bytes(program.to_png())
    assert esolangs.run(language, path, "0\n") == "0"
