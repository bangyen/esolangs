"""Structured output retains IO usage and only declared completion reports."""

import pytest

from esolangs.exceptions import InterpreterLimitError
from esolangs.results import ExecutionResult
from esolangs.runtime._execution import execute_prepared
from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport
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
    assert result[:4] == ("é", 1, 1, 1)
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
    assert caught.value.execution == ExecutionResult("prefix", 0, 0, 0)


@pytest.mark.parametrize("kind", [Completion.HALTED, Completion.POST_HALT])
def test_halted_reports_do_not_accept_cycle_evidence(kind):
    with pytest.raises(ValueError, match="only periodic"):
        CompletionReport(kind, BoundaryCycle(0, 0, 1, 1))


@pytest.mark.parametrize("cycle", [None, object()])
def test_periodic_reports_require_cycle_evidence(cycle):
    with pytest.raises(ValueError, match="requires cycle"):
        CompletionReport(Completion.PERIODIC, cycle)
