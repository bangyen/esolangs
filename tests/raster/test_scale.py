"""Scaling survives PNG round trips, including ambiguous codel grids."""

import pytest

import esolangs
from esolangs.exceptions import ArgumentError, ProgramError
from esolangs.line.extract import detect_scale as line_scale
from esolangs.line.mask import Mask
from esolangs.raster import Raster
from esolangs.raster.scale import detect_scale, normalize


@pytest.mark.medium
@pytest.mark.parametrize("balanced", [False, True])
@pytest.mark.parametrize("scale", [2, 3, 17])
def test_piet_scaled_png_computes_every_row(scale: int, *, balanced: bool) -> None:
    language = esolangs.Language("Piet")
    native = language.generate("0001", balance=balanced)
    enlarged = language.generate("0001", balance=balanced, scale=scale)
    assert isinstance(native, Raster)
    assert isinstance(enlarged, Raster)
    assert len(enlarged.rows) == len(native.rows) * scale
    decoded = Raster.from_png(enlarged.to_png())
    assert detect_scale(decoded.rows) == scale
    assert language.evaluate(decoded, inputs=2) == "0001"
    assert language.run(decoded, "1\n1\n", scale=scale) == "1"


@pytest.mark.medium
@pytest.mark.parametrize("balanced", [False, True])
def test_line_scaled_png_runs(*, balanced: bool) -> None:
    language = esolangs.Language("Line")
    native = language.generate("00", balance=balanced)
    enlarged = language.generate("00", balance=balanced, scale=2)
    assert isinstance(native, Raster)
    assert isinstance(enlarged, Raster)
    assert len(enlarged.rows[0]) == len(native.rows[0]) * 2
    decoded = Raster.from_png(enlarged.to_png())
    assert language.run(decoded, "1\n") == "0"
    assert language.run(decoded, "0\n", scale=2) == "0"


def test_line_detection_has_no_sixteen_fold_ceiling() -> None:
    # A small stroke with uneven outer margins retains its ink-anchored grid.
    mask = Mask(
        40,
        45,
        [0] * 3 + [((1 << 34) - 1) << 5] * 17 + [((1 << 17) - 1) << 5] * 17 + [0] * 3,
    )
    assert line_scale(mask) == 17


@pytest.mark.medium
def test_piet_explicit_scale_resolves_ambiguous_image() -> None:
    red, light, terminal, black = (255, 0, 0), (255, 192, 192), (192, 0, 192), (0, 0, 0)
    logical = Raster(
        ((light, black, terminal), (light, red, terminal), (black, black, terminal))
    )
    image = Raster.from_png(logical.upscaled(2).to_png())
    assert esolangs.run("Piet", image) == "2"
    assert esolangs.run("Piet", image, scale=1) == "8"
    assert esolangs.run("Piet", image, scale=2, isolated=True) == "2"


def test_scale_validation_and_uniformity() -> None:
    image = Raster((((0, 0, 0), (255, 255, 255)), ((0, 0, 0), (0, 0, 0))))
    assert image.upscaled() is image
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
            esolangs.generate("Piet", "00", scale=scale)
    with pytest.raises(ArgumentError, match="raster"):
        esolangs.generate("Brainfuck", "00", scale=2)
    with pytest.raises(ArgumentError, match="raster"):
        esolangs.run("Brainfuck", "+.", scale=1)
    with pytest.raises(ArgumentError, match="raster"):
        esolangs.evaluate("Brainfuck", "+.", inputs=1, scale=1)
    with pytest.raises(ProgramError, match="uniform"):
        esolangs.run("Line", image, scale=2)


def test_monochrome_codel_grid() -> None:
    image = Raster((((255, 0, 0),) * 6,) * 4)
    assert detect_scale(image.rows) == 2
    assert len(normalize(image.rows)) == 2


@pytest.mark.medium
@pytest.mark.parametrize("name", ["Line", "Piet"])
def test_native_adapter_scales_and_runs(name: str) -> None:
    import importlib

    adapter = importlib.import_module(f"esolangs.{name.lower()}")
    image = adapter.generate("00", scale=2)
    assert esolangs.run(name, Raster.from_png(image.to_png()), "1\n") == "0"


@pytest.mark.medium
@pytest.mark.parametrize("name", ["Line", "Piet"])
def test_cli_scaled_png_round_trip(name, monkeypatch, capsysbinary, tmp_path):
    import io
    import sys

    from esolangs.cli import main

    monkeypatch.setattr(
        sys, "argv", ["esolangs", "generate", "--scale", "2", name, "00"]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    main()
    generated = capsysbinary.readouterr()
    assert generated.err == b""
    path = tmp_path / "scaled.png"
    path.write_bytes(generated.out)
    monkeypatch.setattr(
        sys, "argv", ["esolangs", "run", "--scale", "2", name, str(path)]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
    main()
    assert capsysbinary.readouterr().out == b"0"


@pytest.mark.parametrize("value", ["x", "0", "-1", "1.5"])
def test_cli_rejects_invalid_scale(value, monkeypatch, capsys):
    import sys

    from esolangs.cli import main

    monkeypatch.setattr(
        sys, "argv", ["esolangs", "generate", "--scale", value, "Piet", "00"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "--scale must be a positive integer" in capsys.readouterr().err


def test_explicit_line_scale_rejects_partial_ink_blocks() -> None:
    from esolangs.line.extract import normalize_scale

    with pytest.raises(ValueError, match="uniform"):
        normalize_scale(Mask(3, 2, [3, 3, 3]), 2)
    blank = Mask(3, 3)
    assert normalize_scale(blank, 2) is blank


@pytest.mark.medium
def test_explicit_scale_validates_lazy_line_pixels() -> None:
    image = esolangs.generate("Line", "00", scale=2)
    assert isinstance(image, Raster)
    assert esolangs.run("Line", image, "1\n", scale=2) == "0"
    with pytest.raises(ProgramError, match="uniform"):
        esolangs.run("Line", image, "1\n", scale=3)


@pytest.mark.medium
def test_explicit_scale_evaluation_including_isolation() -> None:
    source = esolangs.generate("Piet", "0001", scale=2)
    assert esolangs.evaluate("Piet", source, inputs=2, scale=2) == "0001"
    assert esolangs.evaluate("Piet", source, inputs=2, scale=2, isolated=True) == "0001"


def test_partial_blank_line_scale_group_is_allowed() -> None:
    from esolangs.line.extract import normalize_scale

    mask = Mask(3, 2, [3, 3, 0])
    assert normalize_scale(mask, 2).rows == [1, 0]


def test_empty_piet_operation_path_halts() -> None:
    from esolangs.piet.balance import _emit, _plan

    image = _emit([], _plan([], 13, 14))
    assert esolangs.run("Piet", image) == ""
