"""Replay guards must reject invalid suspended work under normal execution."""

# ruff: noqa: SLF001 -- Exercise the runtime's unconditional invariants.
import pytest

from esolangs.interpreters.grid_based import _circuit_functions as runtime
from esolangs.interpreters.grid_based import circuit_diagram as native
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.circuit_diagram_observer import Factory


def test_replay_cannot_skip_unrecorded_clock_reads():
    clock = runtime._ReplayClock(runtime._TypeClock())
    assert clock.read() == 0
    clock.skip(0)
    with pytest.raises(RuntimeError, match="clock replay exceeds recorded prefix"):
        clock.skip(1)


def test_replay_cannot_change_its_request():
    machine = native._Machine(
        ["{inverse", "-1-~-1-:", "}", "-1-inverse-:"], ScriptedIO("1")
    )
    gate = next(gate for gate in machine.gates if gate.body is not None)
    request = runtime._NeedFunctionError(gate, ((1,),), None, type_only=False)
    work = runtime._FunctionEvaluation(request)
    frame = work.frames[0]
    frame.results[0] = (request.key, ((1,),), (0,), 0)
    assert work.resolve(gate, ((1,),), None, type_only=False) == (0,)
    frame.next_call = 0
    with pytest.raises(RuntimeError, match="function replay changed its request"):
        work.resolve(gate, ((0,),), None, type_only=False)


def test_function_width_cache_preserves_evicted_and_revisited_widths():
    for width in [*range(1, 261), 1, 256, 260]:
        code = ["{inverse", "-n-~-n-:", "}", f"-{width}-inverse-:"]
        Factory(code, native._Machine).check("0" * width, "1" * width)
        assert len(runtime._FUNCTION_WIDTHS) <= 256


def test_suspended_function_replays_its_own_clock_prefix(monkeypatch):
    code = [
        "{inverse",
        "-n-~-n-:",
        "}",
        "{clocked",
        "t-32-inverse-:",
        "",
        "-n-",
        "}",
        "-1-clocked-:",
    ]
    monkeypatch.setattr(native, "_seconds_since_2000", lambda: 5)
    result = Factory(code, native._Machine, clock_seconds=5).check(
        "0", format(0xFFFFFFFF ^ 5, "032b")
    )
    assert result["halted"]
