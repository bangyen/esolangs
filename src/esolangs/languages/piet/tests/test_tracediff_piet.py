"""Trace comparison keeps Piet's explicit codel scale."""

import pytest

import esolangs
from esolangs.languages.piet import interpreter
from esolangs.raster import Raster
from esolangs.registry import LANGUAGES
from tests.tooling.script_support import REPO_ROOT, load

tracediff = load(REPO_ROOT / "scripts" / "tracediff.py")


@pytest.mark.medium
def test_trace_and_timing_keep_artifact_raster_scale(monkeypatch):
    red, light, terminal, black = (255, 0, 0), (255, 192, 192), (192, 0, 192), (0, 0, 0)
    logical = Raster(
        ((light, black, terminal), (light, red, terminal), (black, black, terminal))
    )
    image = Raster.from_png(logical.upscaled(2).to_png())
    program = esolangs.ProgramArtifact(image, "Piet", scale=1)
    prepare = interpreter._prepare_raster
    native, calls, outputs = interpreter._Machine, [], []

    def prepare_raster(source, scale):
        assert source is image
        calls.append(scale)
        return prepare(source, scale)

    def machine(source, io):
        outputs.append(io)
        return native(source, io)

    monkeypatch.setattr(interpreter, "_prepare_raster", prepare_raster)
    monkeypatch.setattr(interpreter, "_Machine", machine)
    explicit = tracediff.trace(
        interpreter, (program, ""), frozenset(), runtime=LANGUAGES["Piet"].runtime
    )
    detected = tracediff.trace(
        interpreter, (image, ""), frozenset(), runtime=LANGUAGES["Piet"].runtime
    )
    assert tracediff._halts(explicit)
    assert tracediff._halts(detected)
    assert explicit[-1][-1] == "8"
    assert detected[-1][-1] == "2"
    assert (
        tracediff._lap(
            interpreter,
            [((program, ""), len(explicit))],
            runtime=LANGUAGES["Piet"].runtime,
        )
        > 0
    )
    assert calls == [1, None, 1]
    assert outputs[-1].getvalue() == "8"
