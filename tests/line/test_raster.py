"""The public raster boundary exercised by the unimplemented Line language."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.line import Raster
from esolangs.line import run as run_line
from esolangs.line.line_boolean import line_boolean
from esolangs.line.render import render


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
    assert raster.grey_rows() == [bytearray([76, 150, 29])]


def test_line_consumes_the_public_raster() -> None:
    canvas = render(line_boolean("01"))
    raster = Raster(
        tuple(tuple((level, level, level) for level in row) for row in canvas.pixels)
    )
    io = ScriptedIO("1\n")
    run_line(raster, io)
    assert io.getvalue() == "1"
