"""Piet through the shared API, CLI and machinery."""

import importlib
from dataclasses import replace

import pytest

import esolangs
from esolangs import Raster
from esolangs._evaluate import _evaluate
from esolangs._execution import interpreter_module
from esolangs.exceptions import TemplateError
from esolangs.registry import LANGUAGES, SourceKind
from tests.api.test_api_contracts import XOR
from tests.interpreters.test_input_convention import assert_reads_tokens_on_one_line
from tests.support.pick import languages


def first_other_raster() -> str:
    """Another raster language than Piet; a skip if there is none."""
    others = [name for name in languages(source_kind="raster") if name != "Piet"]
    if not others:
        pytest.skip("no other raster language is registered")
    return others[0]


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
        """Piet describes its own interpreter rather than another raster's."""
        piet = importlib.import_module("esolangs.interpreters.stack_based.piet")
        other = importlib.import_module(
            "esolangs.interpreters." + LANGUAGES[first_other_raster()].interpreter
        )
        assert esolangs.describe("Piet")["spec"] == (piet.__doc__ or "").strip()
        assert esolangs.describe("Piet")["spec"] != (other.__doc__ or "").strip()


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


@pytest.mark.medium
def test_raster_interpreter_retains_geometry_hint():
    image = Raster((((255, 255, 255),),))
    with pytest.raises(esolangs.ProgramError, match=r".+") as caught:
        esolangs.run("Piet", image, scale=2, timeout=1)
    assert "dividing both image dimensions" in caught.value.__notes__[0]


def test_a_raster_is_refused_as_a_template() -> None:
    """Typed ``Program`` so generate's result type-checks; no raster embeds."""
    with pytest.raises(TemplateError, match="raster programs read"):
        esolangs.instantiate("Piet", esolangs.generate("Piet", XOR), [0, 1])


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


def test_empty_piet_operation_path_halts() -> None:
    from esolangs.tools.piet.balance import _emit, _plan

    image = _emit([], _plan([], 13, 14))
    assert esolangs.run("Piet", image) == ""


@pytest.mark.medium
@pytest.mark.parametrize("scale", [2, 3, 17])
def test_piet_detects_its_scale(scale: int) -> None:
    image = esolangs.generate("Piet", "0001", scale=scale)
    assert _evaluate("Piet", Raster.from_png(image.to_png()), inputs=2) == "0001"


def test_it_reads_numeric_tokens_on_the_same_line() -> None:
    assert_reads_tokens_on_one_line("Piet")
