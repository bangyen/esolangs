"""Scaling survives PNG round trips, including ambiguous codel grids."""

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.exceptions import ArgumentError, ProgramError
from esolangs.raster import Raster
from esolangs.raster.scale import detect_scale, normalize
from tests.pick import languages
from tests.test_language_coupling import REFERENCE

RASTER = languages(source_kind="raster", boolean_generator=True)


@pytest.mark.medium
@pytest.mark.parametrize("name", RASTER)
@pytest.mark.parametrize("balanced", [False, True])
@pytest.mark.parametrize("scale", [2, 3])
def test_scaled_png_computes_every_row(
    name: str, scale: int, *, balanced: bool
) -> None:
    native = esolangs.generate(name, "0001", balance=balanced)
    enlarged = esolangs.generate(name, "0001", balance=balanced, scale=scale)
    assert isinstance(native, Raster)
    assert isinstance(enlarged, Raster)
    assert len(enlarged.rows) == len(native.rows) * scale
    assert len(enlarged.rows[0]) == len(native.rows[0]) * scale
    decoded = Raster.from_png(enlarged.to_png())
    assert _evaluate(name, decoded, inputs=2, scale=scale) == "0001"
    assert _evaluate(name, decoded, inputs=2, scale=scale, isolated=True) == "0001"


def test_generic_detection_finds_a_large_scale() -> None:
    image = esolangs.generate(RASTER[-1], "0001", scale=17)
    assert detect_scale(Raster.from_png(image.to_png()).rows) == 17


@pytest.mark.parametrize("name", RASTER)
def test_scale_validation_and_uniformity(name: str) -> None:
    image = Raster((((0, 0, 0), (255, 255, 255)), ((0, 0, 0), (0, 0, 0))))
    assert image.upscaled(1) is image
    assert normalize(image.rows) is image.rows
    assert image.upscaled(2).language is None
    with pytest.raises(ProgramError, match="uniform"):
        normalize(image.rows, 2)
    with pytest.raises(ProgramError, match="divisible"):
        normalize(image.rows, 3)
    for scale in (True, 0, -1, 1.5, "2", None):
        with pytest.raises(ArgumentError, match="scale"):
            image.upscaled(scale)
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
def test_cli_rejects_invalid_scale(value, monkeypatch, capsys):
    import sys

    from esolangs.cli import main

    argv = ["esolangs", "generate", "--scale", value, RASTER[0], "00"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "--scale must be a positive integer" in capsys.readouterr().err
