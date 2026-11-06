"""Public results preserve output, input accounting and completion across routes."""

import pickle

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.results import Completion, CompletionReport, ExecutionResult
from esolangs.runtime.io import ScriptedIO
from tests.support.pick import first, one_where
from tests.support.reference import REFERENCE

pytestmark = pytest.mark.medium
_ROUTES = [
    {},
    {"max_steps": 10000},
    {"isolated": True},
    {"isolated": True, "max_steps": 10000},
]


@pytest.mark.parametrize(
    "route", [*_ROUTES, *(r | {"max_output": 1} for r in _ROUTES if r.get("isolated"))]
)
def test_result_counts_unicode_characters_and_preserves_unread_input(route):
    result = esolangs.run(REFERENCE, ",.", stdin="éNEXT", **route)
    assert result == ExecutionResult(
        "é",
        1,
        1,
        0,
        CompletionReport(Completion.HALTED),
        2 if "max_steps" in route else None,
    )


@pytest.mark.parametrize("route", _ROUTES)
def test_result_retains_a_caught_eof(route, monkeypatch):
    name = first(
        boolean_generator=True,
        parameterized=False,
        eof_is_a_value=True,
        source_kind="text",
        input_shape="char_stream",
    )
    source = esolangs.generate(name, "01")
    attempts = []

    class ObservedIO(ScriptedIO):
        def input_char(self, prompt="Input: "):
            try:
                return super().input_char(prompt)
            except EOFError:
                attempts.append(True)
                raise

    monkeypatch.setattr(esolangs, "ScriptedIO", ObservedIO)
    native = esolangs.run(name, source)
    assert (native.input_position, native.input_reads) == (0, 0)
    assert attempts, "the EOF control did not perform a read"
    assert native.input_past_end == len(attempts)
    assert esolangs.run(name, source, **route)._replace(steps=None) == native


@pytest.mark.parametrize(
    "name",
    one_where(
        lambda info: info["answer_mode"] != "termination",
        boolean_generator=True,
        dumps_on_the_post_halt_step=True,
        steppable_to_answer=True,
    ),
)
def test_post_halt_result_includes_the_final_dump(name):
    template = esolangs.generate(name, "01")
    source = (
        esolangs.instantiate(name, template, [1])
        if LANGUAGES[name].parameterized
        else template
    )
    stdin = "" if LANGUAGES[name].parameterized else esolangs.encode_inputs(name, [1])
    results = [esolangs.run(name, source, stdin=stdin, **route) for route in _ROUTES]
    assert all(result._replace(steps=None) == results[0] for result in results)
    assert results[1].steps == results[3].steps
    assert results[1].steps is not None
    assert results[0].completion.kind is Completion.POST_HALT
    assert results[0].completion.cycle is None
    assert esolangs.read_answer(name, results[0].output) == "1"
    if LANGUAGES[name].parameterized:
        assert results[0][1:4] == (0, 0, 0)


def test_periodic_result_retains_cycle_evidence_in_a_worker():
    name = first(boolean_generator=True, steppable_to_answer=False)
    template = esolangs.generate(name, "01")
    source = (
        esolangs.instantiate(name, template, [1])
        if LANGUAGES[name].parameterized
        else template
    )
    stdin = "" if LANGUAGES[name].parameterized else esolangs.encode_inputs(name, [1])
    native = esolangs.run(name, source, stdin=stdin)
    assert native.completion.kind is Completion.PERIODIC
    assert native.completion.cycle is not None
    assert esolangs.run(name, source, stdin=stdin, isolated=True) == native


@pytest.mark.parametrize("route", _ROUTES)
@pytest.mark.parametrize(("source", "stdin"), [(",", ""), (",.,", "é")])
def test_result_failures_still_raise_with_partial_output(route, source, stdin):
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run(REFERENCE, source, stdin=stdin, **route)
    assert caught.value.partial_output == stdin
    assert caught.value.execution == ExecutionResult(
        stdin,
        len(stdin),
        len(stdin),
        1,
        steps=2 * len(stdin) if "max_steps" in route else None,
    )


def test_bound_language_returns_the_same_record():
    bound = esolangs.Language(REFERENCE)
    result = bound.run(
        ",.", stdin="éNEXT", max_steps=2, isolated=True, max_output=1, timeout=5
    )
    assert result.steps == 2
    assert result._replace(steps=None) == esolangs.run(REFERENCE, ",.", stdin="éNEXT")


def test_public_record_is_immutable_and_the_old_import_is_retired():
    from importlib import import_module

    assert esolangs.ExecutionResult is ExecutionResult
    assert not hasattr(esolangs, "run_result")
    assert not hasattr(esolangs.Language, "run_result")
    assert not hasattr(esolangs, "compat")
    assert not hasattr(esolangs, "_recover_template")
    for owner in (esolangs, esolangs.Language):
        assert not hasattr(owner, "generate_artifact")
        assert not hasattr(owner, "load_artifact")
    from esolangs import registry

    assert not hasattr(registry, "recover_setters")
    for retired in ("esolangs.runtime._result", "esolangs.compat", "esolangs.tagged"):
        with pytest.raises(ModuleNotFoundError) as missing:
            import_module(retired)
        assert missing.value.name == retired
    from esolangs import _cycles, vm

    for retired in (
        "_AffineMachine",
        "_branch_search",
        "_BranchingStepMachine",
        "_checked_unwrap",
        "_clamps_hold",
        "_climbs_forever",
        "_FramedMachine",
        "_grows_forever",
        "_GrowthVisit",
        "_refuse_random",
        "_Snapshot",
        "_StepMachine",
        "_SteppableMachine",
        "_TapeMachine",
        "_unwrap",
        "_Visit",
    ):
        assert getattr(_cycles, retired) is not None
        assert not hasattr(vm, retired), retired
        with pytest.raises(ImportError, match=retired):
            exec(f"from esolangs.vm import {retired}", {})
    result = ExecutionResult("custom", None, None, None)
    assert result.completion is None
    assert pickle.loads(pickle.dumps(result)) == result
    with pytest.raises(AttributeError):
        result.output = "changed"
