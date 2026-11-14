"""Structured output retains IO usage and only declared completion reports."""

import sys
from fractions import Fraction

import pytest

from esolangs import BooleanEvaluation, ExecutionLimits, ExecutionOutcome
from esolangs.exceptions import (
    ArgumentError,
    InputExhaustedError,
    InterpreterLimitError,
)
from esolangs.results import ExecutionResult
from esolangs.runtime._execution import execute_prepared
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
from esolangs.runtime._proof import BranchProof, CycleDecision
from esolangs.runtime.io import ScriptedIO
from tests.support.reference import REFERENCE


def test_result_retains_character_cursor_reads_and_caught_eof():
    report = CompletionReport(Completion.HALTED)

    def execute(_source, io):
        io.print_char(chr(io.input_char()))
        with pytest.raises(EOFError):
            io.input_char()
        return report

    result = execute_prepared(REFERENCE, execute, "", ScriptedIO("é")).unwrap()
    assert (
        result.output,
        result.input_position,
        result.input_reads,
        result.input_past_end,
    ) == ("é", 1, 1, 1)
    assert result.completion is report
    with pytest.raises(AttributeError):
        result.output = "changed"


@pytest.mark.parametrize("value", [None, Completion.HALTED, True])
def test_a_return_without_a_report_is_not_completion(value):
    with pytest.raises(InterpreterLimitError, match="no completion report"):
        execute_prepared(REFERENCE, lambda *_: value, "", ScriptedIO()).unwrap()


def test_declared_runner_requires_a_report_and_keeps_partial_output():
    def execute(_source, io):
        io.print_str("prefix")

    outcome = execute_prepared(REFERENCE, execute, "", ScriptedIO())
    assert outcome.status == "limit"
    assert outcome.observation.completion is None
    with pytest.raises(InterpreterLimitError, match="no completion report") as caught:
        outcome.unwrap()
    assert caught.value is outcome.error
    assert caught.value.partial_output == "prefix"
    assert caught.value.observation == ExecutionResult("prefix", 0, 0, 0)


@pytest.mark.parametrize("kind", [Completion.HALTED, Completion.POST_HALT])
def test_halted_reports_do_not_accept_cycle_evidence(kind):
    with pytest.raises(ValueError, match="only periodic"):
        CompletionReport(kind, BoundaryCycle(0, 0, 1, 1))


@pytest.mark.parametrize("cycle", [None, object()])
def test_periodic_reports_require_cycle_evidence(cycle):
    with pytest.raises(ValueError, match="requires cycle"):
        CompletionReport(Completion.PERIODIC, cycle)


def test_public_records_require_valid_evidence() -> None:
    for fields in (
        (None, 0, 0, 0),
        ("", -1, 0, 0),
        ("", None, True, None),
        ("", 0, None, 0),
    ):
        with pytest.raises(ArgumentError, match=r"execution result|counter"):
            ExecutionResult(*fields)
    with pytest.raises(ArgumentError, match="completion evidence"):
        ExecutionResult("", 0, 0, 0, completion="halted")
    with pytest.raises(ArgumentError, match="invalid execution counter"):
        ExecutionResult("", 0, 0, 0, steps=-1)
    unfinished = ExecutionResult("", 0, 0, 0)
    completed = ExecutionResult(
        "0", 0, 0, 0, completion=CompletionReport(Completion.HALTED)
    )
    proof = CycleDecision(halts=True, commands=0)
    assert BooleanEvaluation("0", completed).answer == "0"
    assert BooleanEvaluation("1", unfinished, termination=proof).termination is proof
    with pytest.raises(ArgumentError, match="answer bit"):
        BooleanEvaluation("2", completed)
    with pytest.raises(ArgumentError, match="completion evidence"):
        BooleanEvaluation("1", unfinished)
    with pytest.raises(ArgumentError, match="decision evidence"):
        BooleanEvaluation("1", unfinished, termination=True)
    with pytest.raises(ArgumentError, match="unfinalized"):
        BooleanEvaluation("1", completed, termination=proof)


def test_execution_record_repr_keeps_ordinary_diagnostics() -> None:
    assert repr(ExecutionLimits(max_steps=3)) == (
        "ExecutionLimits(preparation_timeout=None, execution_timeout=None, "
        "total_timeout=None, max_steps=3, max_output=None, max_memory=None)"
    )
    assert repr(ExecutionResult("é", 1, 1, 0)) == (
        "ExecutionResult(output='é', input_position=1, input_reads=1, "
        "input_past_end=0, completion=None, steps=None)"
    )
    assert repr(BoundaryCycle((3,), 1, 2, 1)) == (
        "BoundaryCycle(state=(3,), first_pass=1, repeat_pass=2, commands_per_pass=1)"
    )
    assert repr(CycleDecision(halts=True, commands=3)) == (
        "CycleDecision(halts=True, commands=3, cycle=None, branches=None)"
    )


def test_execution_records_repr_large_counts_and_nested_evidence() -> None:
    count = 1 << 18000
    spelling = hex(count)
    cap = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        with pytest.raises(ValueError, match="Exceeds the limit"):
            repr(count)
        limits = ExecutionLimits(max_steps=count, max_output=count, max_memory=count)
        cycle = BoundaryCycle((frozenset({count}), Fraction(count, 3)), 1, count, 1)
        completed = ExecutionResult(
            "",
            count,
            count,
            0,
            completion=CompletionReport(Completion.PERIODIC, cycle),
            steps=count,
        )
        observed = ExecutionResult("", count, count, 1, steps=count)
        verdict = CycleDecision(halts=True, commands=count)
        branch = BranchProof(count, ((count, (count,)),), halts=False)
        error = InputExhaustedError(count, count)

        assert f"max_steps={spelling}" in repr(limits)
        assert f"Fraction({spelling}, 3)" in repr(completed)
        assert f"repeat_pass={spelling}" in repr(
            ExecutionOutcome("completed", completed)
        )
        assert f"commands={spelling}" in repr(
            BooleanEvaluation("0", observed, termination=verdict)
        )
        assert f"root={spelling}" in repr(branch)
        assert f"{spelling} lines supplied" in str(error)
        assert hex(count + 1) in error.__notes__[0]
    finally:
        sys.set_int_max_str_digits(cap)
