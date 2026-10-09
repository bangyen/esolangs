"""Line through the shared API, CLI and machinery."""

import json

import pytest

import esolangs
from esolangs import DialectSettings, Raster
from esolangs._evaluate import _evaluate
from esolangs.tui import History, render
from tests.cli.test_cli_portable import save_generated
from tests.test_tui import _highlighted


@pytest.mark.medium
@pytest.mark.parametrize("scale", [1, 2])
def test_cli_scaled_raster(tmp_path, capsys, scale):
    settings = DialectSettings()
    path = save_generated(tmp_path, capsys, "Line", settings, "--scale", str(scale))
    restored = esolangs.load_program("Line", path.read_text(encoding="utf-8"))
    assert _evaluate("Line", restored, inputs=2) == "0110"


@pytest.mark.medium
@pytest.mark.parametrize("scale", [1, 2])
def test_raw_png_round_trip_executes(scale):
    settings = DialectSettings()
    source = esolangs.generate("Line", "01", scale=scale, settings=settings)
    raw = Raster.from_png(source.to_png())
    assert raw.settings is None
    restored = esolangs.load_program(
        "Line", esolangs.dump_program("Line", raw, settings=settings)
    )
    assert restored.rows == source.rows
    assert _evaluate("Line", restored, inputs=1) == "01"


@pytest.mark.parametrize("value", ["!", "abcd", "é"])
def test_invalid_png(value):
    document = json.loads(
        esolangs.dump_program("Line", esolangs.generate("Line", "01"))
    )
    document["source"] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Line", json.dumps(document))


@pytest.mark.medium
def test_line_highlight_tracks_ink_after_crop_and_scale() -> None:
    from esolangs import generate
    from esolangs.raster import Raster

    source = generate("Line", "01", scale=3)
    assert isinstance(source, Raster)
    history = History("Line", Raster.from_png(source.to_png()), "1\n")
    for step in range(100):
        frame = history.at(step)
        if frame.halted:
            assert frame.output == "1"
            break
        assert _highlighted(render(frame)) == "#"
    else:
        pytest.fail("identity did not halt within 100 steps")
