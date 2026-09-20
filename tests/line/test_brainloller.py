"""Brainloller proves the public raster type preserves command colours."""

import pytest

from esolangs.line import Raster
from esolangs.line import run as run_line
from esolangs.line.brainloller import decode, encode
from esolangs.line.line_boolean import line_boolean
from esolangs.line.render import render
from esolangs.interpreters.io import ScriptedIO


def test_linear_program_survives_png_round_trip() -> None:
    """Every fixed-palette Brainfuck command remains exact through PNG."""
    code = "><+-.,[]"
    raster = encode(code)
    assert decode(Raster.from_png(raster.to_png())) == code


def test_turns_define_a_two_dimensional_path() -> None:
    """Clockwise and counter-clockwise pixels redirect the instruction pointer."""
    white = (255, 255, 255)
    clockwise = (0, 255, 255)
    counterclockwise = (0, 128, 128)
    plus = (0, 255, 0)
    output = (0, 0, 255)
    raster = Raster(
        (
            (plus, clockwise, white),
            (white, counterclockwise, output),
        )
    )
    assert decode(raster) == "+."


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
