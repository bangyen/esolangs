"""Piet through the shared API, CLI and machinery."""

import importlib
from dataclasses import replace

import pytest

import esolangs
from esolangs import Raster, run
from esolangs.exceptions import TemplateError
from esolangs.operations.source import _check_program
from esolangs.registry import CATALOG, LANGUAGES
from tests.support.evaluation import _evaluate
from tests.support.execution import termination_observed
from tests.support.input_convention import assert_reads_tokens_on_one_line
from tests.support.pick import languages
from tests.support.witness_tables import XOR


def first_other_raster() -> str:
    """Another raster language than Piet; a skip if there is none."""
    others = [name for name in languages(source_kind="raster") if name != "Piet"]
    if not others:
        pytest.skip("no other raster language is registered")
    return others[0]


def test_bound_raster_language_loads_and_evaluates_png(tmp_path) -> None:
    language = esolangs.Language("Piet")
    program = language.generate("0110").source
    assert isinstance(program, esolangs.Raster)
    path = tmp_path / "program.png"
    path.write_bytes(program.to_png())
    assert _evaluate(language.name, path, inputs=2) == "0110"


def test_a_raster_is_not_a_path() -> None:
    """Raster source keeps its declared representation at acquisition."""
    program = esolangs.generate("Piet", "01")
    assert _check_program("Piet", program.source).source is program.source


def test_raster_interpreter_owns_loading_and_scale_support() -> None:
    program = esolangs.generate("Piet", "01", scale=2)
    catalog = CATALOG.with_language(replace(LANGUAGES["Piet"], backend=None))
    assert (
        run("Piet", program.source.to_png(), stdin="1", scale=2, catalog=catalog).output
        == "1"
    )
    assert (
        run("Piet", program, stdin="1", scale=2, max_steps=100, catalog=catalog).output
        == "1"
    )


class TestSpecAbortsRatherThanReturningNothing:
    """``-OO`` strips docstrings, and ``spec`` read one."""

    def test_a_raster_language_returns_its_own_module_docstring(self) -> None:
        """Piet describes its own interpreter rather than another raster's."""
        piet = importlib.import_module("esolangs.languages.piet.interpreter")
        other = importlib.import_module(
            f"esolangs.languages.{LANGUAGES[first_other_raster()].id}.interpreter"
        )
        assert esolangs.describe("Piet")["spec"] == (piet.__doc__ or "").strip()
        assert esolangs.describe("Piet")["spec"] != (other.__doc__ or "").strip()


@pytest.mark.medium
def test_raster_interpreter_retains_geometry_hint() -> None:
    image = Raster((((255, 255, 255),),))
    with pytest.raises(esolangs.ProgramError, match=r".+") as caught:
        run("Piet", image, scale=2, timeout=1)
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
    assert run("Piet", image).output == "2"
    assert run("Piet", image, scale=1).output == "8"
    assert run("Piet", image, scale=2, isolated=True).output == "2"
    _check_worker_proof_scale(image)


def _check_worker_proof_scale(image: Raster) -> None:
    from esolangs.debugger import make_debugger
    from esolangs.runtime._isolated import termination_result_isolated
    from esolangs.vm import _capture_observation
    from tests.support.certification_barrier import guarded_worker
    from tests.support.reference import REFERENCE

    explicit = esolangs.ProgramArtifact(image, "Piet", scale=1)
    default = termination_observed("Piet", image, "", 5)
    scaled = termination_observed("Piet", explicit, "", 5)
    assert (default.observation.output, scaled.observation.output) == ("2", "8")
    with guarded_worker(expected=2):
        assert termination_result_isolated("Piet", image, "", 5) == default
        assert termination_result_isolated("Piet", explicit, "", 5) == scaled
    debugger = make_debugger("Piet", explicit)
    assert scaled.decision.commands is not None
    for _ in range(scaled.decision.commands):
        assert not debugger.halted
        debugger.step()
    assert debugger.halted
    assert debugger.observation.steps == scaled.decision.commands
    assert _capture_observation(debugger.vm) == scaled.observation
    with pytest.raises(esolangs.ProgramError, match="generated for Piet"):
        termination_result_isolated(REFERENCE, explicit, "", 5)


def test_empty_piet_operation_path_halts() -> None:
    from esolangs.languages.piet.generator.balance import _emit, _plan

    image = _emit([], _plan([], 13, 14))
    assert run("Piet", image).output == ""


@pytest.mark.medium
@pytest.mark.parametrize("scale", [2, 17])
def test_piet_detects_its_scale(scale: int) -> None:
    image = esolangs.generate("Piet", "0001", scale=scale)
    assert _evaluate("Piet", Raster.from_png(image.source.to_png()), inputs=2) == "0001"


def test_it_reads_numeric_tokens_on_the_same_line() -> None:
    assert_reads_tokens_on_one_line("Piet")
