"""Structured output retains IO usage and only declared completion reports."""

import pytest

from esolangs.exceptions import InterpreterLimitError
from esolangs.runtime._execution import run_prepared
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

    result = run_prepared(
        REFERENCE, execute, "", ScriptedIO("é"), None, report_required=True
    )
    assert result.output == "é"
    assert (result.input_position, result.input_reads, result.input_past_end) == (
        1,
        1,
        1,
    )
    assert result.completion is report
    with pytest.raises(AttributeError):
        result.output = "changed"


@pytest.mark.parametrize("value", [None, CompletionReport(Completion.HALTED)])
def test_undeclared_completion_stays_unknown(value):
    result = run_prepared(
        REFERENCE, lambda *_: value, "", ScriptedIO(), None, report_required=False
    )
    assert result.output == ""
    assert result.completion is None


def test_declared_runner_requires_a_report_and_keeps_partial_output():
    def execute(_source, io):
        io.print_str("prefix")

    with pytest.raises(InterpreterLimitError, match="no completion report") as caught:
        run_prepared(REFERENCE, execute, "", ScriptedIO(), None, report_required=True)
    assert caught.value.partial_output == "prefix"


@pytest.mark.parametrize("kind", [Completion.HALTED, Completion.POST_HALT])
def test_halted_reports_do_not_accept_cycle_evidence(kind):
    with pytest.raises(ValueError, match="only periodic"):
        CompletionReport(kind, BoundaryCycle(0, 0, 1, 1))


@pytest.mark.parametrize("cycle", [None, object()])
def test_periodic_reports_require_cycle_evidence(cycle):
    with pytest.raises(ValueError, match="requires cycle"):
        CompletionReport(Completion.PERIODIC, cycle)
