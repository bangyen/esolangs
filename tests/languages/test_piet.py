"""Piet through the shared API, CLI and machinery."""

from dataclasses import replace

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.registry import LANGUAGES, SourceKind


def test_bound_raster_language_loads_and_evaluates_png(tmp_path):
    language = esolangs.Language("Piet")
    program = language.generate("0110")
    assert isinstance(program, esolangs.Raster)
    path = tmp_path / "program.png"
    path.write_bytes(program.to_png())
    assert _evaluate(language.name, path, inputs=2) == "0110"


def test_a_raster_is_not_a_path() -> None:
    """``_looks_like_a_path`` is typed for text; a Raster must answer False."""
    program = esolangs.generate("Piet", "01")
    assert not esolangs._looks_like_a_path(program)  # noqa: SLF001


def test_raster_interpreter_owns_loading_and_scale_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = esolangs.generate("Piet", "01", scale=2)
    monkeypatch.setitem(
        LANGUAGES,
        "Piet",
        replace(LANGUAGES["Piet"], source_kind=SourceKind.TEXT, boolean=None),
    )
    assert esolangs.run("Piet", program.to_png(), stdin="1", scale=2) == "1"
    assert esolangs.run("Piet", program, stdin="1", scale=2, max_steps=100) == "1"
