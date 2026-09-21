"""The public raster boundary exercised by Line."""

from pathlib import Path

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.line import run as run_line
from esolangs.line.line_boolean import line_boolean
from esolangs.line.render import render
from esolangs.raster import Raster


def test_png_round_trip_preserves_rgb() -> None:
    raster = Raster((((255, 0, 0), (0, 255, 0), (0, 0, 255)),))
    assert Raster.from_png(raster.to_png()) == raster


def test_raster_rejects_non_rectangular_rows() -> None:
    with pytest.raises(ValueError, match="equal-width"):
        Raster((((0, 0, 0),), ()))


def test_raster_rejects_an_invalid_channel() -> None:
    with pytest.raises(ValueError, match="8-bit RGB"):
        Raster((((0, 0, 256),),))


def test_raster_converts_to_greyscale() -> None:
    raster = Raster((((255, 0, 0), (0, 255, 0), (0, 0, 255)),))
    from esolangs.line import _grey_rows

    assert _grey_rows(raster.rows) == [bytearray([76, 150, 29])]


@pytest.mark.medium
def test_line_consumes_the_public_raster() -> None:
    canvas = render(line_boolean("01"))
    raster = Raster(
        tuple(tuple((level, level, level) for level in row) for row in canvas.pixels)
    )
    io = ScriptedIO("1\n")
    run_line(raster, io)
    assert io.getvalue() == "1"


def test_line_is_a_public_raster_language() -> None:
    program = esolangs.generate("Line", "01")
    assert isinstance(program, Raster)
    assert esolangs.describe("Line")["source_kind"] == "raster"
    assert esolangs.run("Line", program, "1\n") == "1"


@pytest.mark.slow
def test_public_run_loads_line_png(tmp_path: Path) -> None:
    program = esolangs.generate("Line", "01")
    assert isinstance(program, Raster)
    path = tmp_path / "line.png"
    path.write_bytes(program.to_png())
    assert esolangs.run("Line", path, "0\n") == "0"
