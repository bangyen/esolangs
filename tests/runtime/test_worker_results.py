"""Worker results retain counters and immutable periodic evidence."""

import json

import pytest

import esolangs
from esolangs import compat
from esolangs.registry import LANGUAGES
from esolangs.runtime._isolated import _decode
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
from esolangs.runtime._result import ExecutionResult
from esolangs.runtime._result_wire import decode_result, encode_result
from tests.support.pick import one, one_where
from tests.support.reference import REFERENCE


@pytest.mark.parametrize("max_output", [None, 1])
def test_worker_retains_actual_unicode_input_usage(max_output):
    result = esolangs._run_result(
        REFERENCE, ",.", stdin="é", isolated=True, max_output=max_output
    )
    assert result == esolangs._run_result(REFERENCE, ",.", stdin="é")
    assert result[:4] == ("é", 1, 1, 0)


@pytest.mark.parametrize(
    "language",
    [
        *one_where(
            lambda info: info["answer_mode"] != "termination",
            dumps_on_the_post_halt_step=True,
        ),
        *one(steppable_to_answer=False),
    ],
)
def test_declared_completion_survives_a_worker(language):
    template = compat.generate(language, "01")
    source = (
        compat.instantiate(language, template, [1])
        if LANGUAGES[language].parameterized
        else template
    )
    stdin = (
        ""
        if LANGUAGES[language].parameterized
        else esolangs.encode_inputs(language, [1])
    )
    native = esolangs._run_result(language, source, stdin=stdin)
    assert native.completion is not None
    assert esolangs.read_answer(language, native.output) == "1"
    assert esolangs._run_result(language, source, stdin=stdin, isolated=True) == native


def test_immutable_cycle_state_survives_json():
    state = (frozenset({((1, -2), 3), ((4, 5), 6)}), b"\x00\xff", None, True)
    result = ExecutionResult(
        "output",
        2,
        1,
        3,
        CompletionReport(Completion.PERIODIC, BoundaryCycle(state, 1, 3, 7)),
    )
    metadata = json.loads(json.dumps(encode_result(result)))
    assert decode_result(result.output, metadata) == result
    assert hash(decode_result(result.output, metadata).completion.cycle.state) == hash(
        state
    )


@pytest.mark.parametrize("counter", [-1, True])
@pytest.mark.parametrize("failure", [False, True])
def test_worker_refuses_corrupt_counters_and_retains_output(counter, failure):
    metadata = encode_result(ExecutionResult("prefix", 0, 0, 0))
    metadata["input_reads"] = counter
    message = (
        {"error": "HaltError", "args": ["bad"]} if failure else {"result": "prefix"}
    )
    text = (
        json.dumps({"output": "prefix"})
        + "\n"
        + json.dumps({**message, "execution": metadata})
    )
    with pytest.raises(
        esolangs.InterpreterLimitError, match="invalid isolated"
    ) as caught:
        _decode(text, expired=False)
    assert caught.value.partial_output == "prefix"


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("max_steps", [None, 16])
def test_routes_retain_success_and_failed_input_observations(isolated, max_steps):
    options = {"isolated": isolated, "max_steps": max_steps}
    success = esolangs._run_result(REFERENCE, ",.", stdin="é", **options)
    steps = 2 if max_steps is not None else None
    assert success == ExecutionResult(
        "é", 1, 1, 0, CompletionReport(Completion.HALTED), steps
    )
    for source, stdin, expected in (
        (",", "", ExecutionResult("", 0, 0, 1)),
        (",.,", "é", ExecutionResult("é", 1, 1, 1)),
    ):
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            esolangs._run_result(REFERENCE, source, stdin=stdin, **options)
        observed = (
            expected._replace(steps=0 if source == "," else 2)
            if max_steps is not None
            else expected
        )
        assert caught.value.execution == observed
        assert caught.value.partial_output == expected.output


@pytest.mark.parametrize("isolated", [False, True])
def test_step_bound_retains_an_unfinished_observation(isolated):
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        esolangs._run_result(REFERENCE, "+[.]", max_steps=4, isolated=isolated)
    assert caught.value.execution == ExecutionResult("\x01", 0, 0, 0, steps=4)
    assert caught.value.partial_output == "\x01"


def test_failed_worker_cannot_claim_completion():
    metadata = encode_result(
        ExecutionResult("", 0, 0, 0, CompletionReport(Completion.HALTED))
    )
    text = json.dumps({"error": "HaltError", "args": ["bad"], "execution": metadata})
    with pytest.raises(esolangs.InterpreterLimitError, match="invalid isolated"):
        _decode(text, expired=False)


def test_periodic_wire_report_cannot_drop_its_evidence():
    metadata = encode_result(ExecutionResult("", 0, 0, 0))
    metadata["completion"] = {"kind": "periodic", "cycle": None}
    with pytest.raises(ValueError, match="requires cycle"):
        decode_result("", metadata)


def test_normal_worker_cannot_omit_result_metadata(monkeypatch):
    from esolangs.runtime import _isolated

    monkeypatch.setattr(
        _isolated,
        "_launch",
        lambda *_args, **_kwargs: ExecutionResult("prefix", 0, 0, 0),
    )
    with pytest.raises(
        esolangs.InterpreterLimitError, match="omitted execution"
    ) as caught:
        _isolated.run_isolated_result(REFERENCE, "+.")
    assert caught.value.partial_output == "prefix"


@pytest.mark.parametrize(
    "language", [name for name, lang in LANGUAGES.items() if lang.runtime.random]
)
def test_seeded_worker_result_matches_native(language):
    template = compat.generate(language, "01")
    parameterized = LANGUAGES[language].parameterized
    source = compat.instantiate(language, template, [1]) if parameterized else template
    stdin = "" if parameterized else esolangs.encode_inputs(language, [1])
    native = esolangs._run_result(language, source, stdin=stdin, seed=7)
    worker = esolangs._run_result(
        language,
        source,
        stdin=stdin,
        seed=7,
        isolated=True,
        timeout=5,
        max_output=len(native.output),
    )
    assert worker == native
    assert esolangs.read_answer(language, worker.output) == "1"
