"""Piet through the shared API, CLI and machinery."""

import importlib
from dataclasses import replace

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs._execution import interpreter_module
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


class TestSpecAbortsRatherThanReturningNothing:
    """``-OO`` strips docstrings, and ``spec`` read one."""

    def test_it_raises_when_there_is_no_docstring(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulated by emptying one, since the test run is not under -OO."""
        module = interpreter_module("brainfuck")
        monkeypatch.setattr(module, "__doc__", None)
        with pytest.raises(esolangs.ProgramError, match="-OO"):
            esolangs.describe("brainfuck")["spec"]

    def test_it_still_returns_the_text_normally(self) -> None:
        """The abort must not have eaten the ordinary path."""
        assert esolangs.describe("brainfuck")["spec"].startswith("Interpreter for")

    def test_a_raster_language_returns_its_own_module_docstring(self) -> None:
        """Piet describes its own interpreter rather than Line's."""
        piet = importlib.import_module("esolangs.interpreters.stack_based.piet")
        line = importlib.import_module("esolangs.interpreters.tape_based.line")
        assert esolangs.describe("Piet")["spec"] == (piet.__doc__ or "").strip()
        assert esolangs.describe("Piet")["spec"] != (line.__doc__ or "").strip()


@pytest.mark.parametrize(
    "operation",
    [
        lambda huge: esolangs.run("brainfuck", "", timeout=huge),
        lambda huge: esolangs.run("brainfuck", "", timeout=-huge),
        lambda huge: esolangs.run("brainfuck", "", isolated=True, max_output=-huge),
        lambda huge: esolangs.generate("brainfuck", "01", width=-huge),
        lambda huge: esolangs.encode_inputs("brainfuck", [huge]),
        lambda huge: esolangs.encode_inputs("brainfuck", [True, huge]),
        lambda huge: esolangs.run(
            "Piet", esolangs.Raster((((0, 0, 0),),)), scale=-huge
        ),
        lambda huge: esolangs.run("brainfuck", "", timeout={"value": huge}),
    ],
)
def test_oversized_integer_arguments_keep_public_errors(operation):
    with pytest.raises(esolangs.ArgumentError) as caught:
        operation(10**5000)
    assert len(str(caught.value)) < 400
