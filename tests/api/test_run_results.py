"""Public results preserve output, input accounting and completion across routes."""

import pickle

import pytest

import esolangs
from esolangs import compat
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


@pytest.mark.parametrize("route", _ROUTES)
def test_result_counts_unicode_characters_and_preserves_unread_input(route):
    result = esolangs.run_result(REFERENCE, ",.", stdin="éNEXT", **route)
    assert result == ExecutionResult(
        "é",
        1,
        1,
        0,
        CompletionReport(Completion.HALTED),
        2 if "max_steps" in route else None,
    )
    assert compat.run(REFERENCE, ",.", stdin="éNEXT", **route) == result.output


@pytest.mark.parametrize("route", _ROUTES)
def test_result_retains_a_caught_eof(route, monkeypatch):
    name = first(
        boolean_generator=True,
        parameterized=False,
        eof_is_a_value=True,
        source_kind="text",
        input_shape="char_stream",
    )
    source = compat.generate(name, "01")
    attempts = []

    class ObservedIO(ScriptedIO):
        def input_char(self, prompt="Input: "):
            try:
                return super().input_char(prompt)
            except EOFError:
                attempts.append(True)
                raise

    monkeypatch.setattr(esolangs, "ScriptedIO", ObservedIO)
    native = esolangs.run_result(name, source)
    assert (native.input_position, native.input_reads) == (0, 0)
    assert attempts, "the EOF control did not perform a read"
    assert native.input_past_end == len(attempts)
    assert esolangs.run_result(name, source, **route)._replace(steps=None) == native


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
    template = compat.generate(name, "01")
    source = (
        compat.instantiate(name, template, [1])
        if LANGUAGES[name].parameterized
        else template
    )
    stdin = "" if LANGUAGES[name].parameterized else esolangs.encode_inputs(name, [1])
    results = [
        esolangs.run_result(name, source, stdin=stdin, **route) for route in _ROUTES
    ]
    assert all(result._replace(steps=None) == results[0] for result in results)
    assert results[1].steps == results[3].steps
    assert results[1].steps is not None
    assert results[0].completion.kind is Completion.POST_HALT
    assert results[0].completion.cycle is None
    assert esolangs.read_answer(name, results[0].output) == "1"


def test_periodic_result_retains_cycle_evidence_in_a_worker():
    name = first(boolean_generator=True, steppable_to_answer=False)
    template = compat.generate(name, "01")
    source = (
        compat.instantiate(name, template, [1])
        if LANGUAGES[name].parameterized
        else template
    )
    stdin = "" if LANGUAGES[name].parameterized else esolangs.encode_inputs(name, [1])
    native = esolangs.run_result(name, source, stdin=stdin)
    assert native.completion.kind is Completion.PERIODIC
    assert native.completion.cycle is not None
    assert esolangs.run_result(name, source, stdin=stdin, isolated=True) == native


@pytest.mark.parametrize("route", _ROUTES)
def test_result_failures_still_raise_with_partial_output(route):
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run_result(REFERENCE, ",.,", stdin="é", **route)
    assert caught.value.partial_output == "é"
    assert caught.value.execution == ExecutionResult(
        "é", 1, 1, 1, steps=2 if "max_steps" in route else None
    )


def test_bound_language_returns_the_same_record():
    bound = esolangs.Language(REFERENCE)
    result = bound.run_result(
        ",.", stdin="éNEXT", max_steps=2, isolated=True, max_output=1, timeout=5
    )
    assert result.steps == 2
    assert result._replace(steps=None) == esolangs.run_result(
        REFERENCE, ",.", stdin="éNEXT"
    )


def test_public_record_is_immutable_and_keeps_the_internal_import():
    from esolangs.runtime._result import ExecutionResult as InternalResult

    assert InternalResult is esolangs.ExecutionResult is ExecutionResult
    result = ExecutionResult("custom", None, None, None)
    assert result.completion is None
    assert pickle.loads(pickle.dumps(result)) == result
    with pytest.raises(AttributeError):
        result.output = "changed"
