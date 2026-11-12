"""Guarded calls retain values; only evidenced decisions become termination answers."""

import signal
import time

import pytest

import esolangs
import esolangs.runtime._execution as _execution_runtime
from esolangs.results import ExecutionResult
from esolangs.runtime import _termination
from esolangs.runtime.io import ScriptedIO
from tests.support.execution import run_guard
from tests.support.reference import REFERENCE

_ALARM = pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="requires SIGALRM")
_BOUNDS = [None, pytest.param(1, marks=_ALARM)]


@pytest.mark.parametrize("bound", _BOUNDS)
@pytest.mark.parametrize("value", [None, False, object()])
def test_return_identity_and_io_survive_the_guard(bound, value):
    io = ScriptedIO("xy")

    def call(program, channel):
        assert program == "source"
        channel.print_char(chr(channel.input_char()))
        return value

    assert run_guard(call, "source", io, bound) is value
    assert io.getvalue() == "x"
    assert io.position() == 1
    assert io.reads == 1


@pytest.mark.parametrize("bound", _BOUNDS)
def test_a_guard_does_not_replace_a_runner_fault(bound):
    fault = ValueError("runner fault")

    def call(*_args):
        raise fault

    with pytest.raises(ValueError, match="runner fault") as caught:
        run_guard(call, "", ScriptedIO(), bound)
    assert caught.value is fault


@_ALARM
def test_an_expired_call_does_not_return_a_false_verdict():
    def call(*_args):
        time.sleep(1)
        return False

    with pytest.raises(esolangs.ExecutionTimeoutError):
        run_guard(call, "", ScriptedIO(), 0.01)


@pytest.mark.parametrize("verdict", [None, False, True])
def test_termination_returns_without_evidence_abort(monkeypatch, verdict):
    def stop_without_proof(vm):
        vm.step()
        vm.step()
        return verdict

    monkeypatch.setattr(_termination, "_halt_or_cycle_result", stop_without_proof)
    with pytest.raises(
        esolangs.InterpreterLimitError, match="no decision evidence"
    ) as caught:
        _termination._termination_result(REFERENCE, ",.", "A")
    assert caught.value.partial_output == "A"
    assert caught.value.observation == ExecutionResult("A", 1, 1, 0)


def test_a_driver_that_never_ran_does_not_prove_divergence(monkeypatch):
    monkeypatch.setattr(_execution_runtime, "invoke", lambda *_args: None)
    with pytest.raises(esolangs.InterpreterLimitError, match="no decision evidence"):
        _termination._termination_result(REFERENCE, "", "")
