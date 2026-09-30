"""Counterexamples to the withdrawn global behaviour-count certificates."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine


def _result(code: str) -> tuple[str, str]:
    """Execute a closed witness; a repeated complete state proves divergence."""
    io = ScriptedIO()
    machine = _Machine(code, io)
    seen: set[tuple[object, ...]] = set()
    for _ in range(64):
        if machine.halted:
            return "halt", io.getvalue()
        state = machine.snapshot()
        if state in seen:
            return "diverge", ""
        seen.add(state)
        machine.step()
    raise AssertionError("witness neither halted nor repeated a state")


@pytest.mark.parametrize("prefix", ["-", "[-]"])
def test_read_free_prefix_can_zero_the_empty_loop_test(prefix: str) -> None:
    # Both withdrawn certificates discarded [Y[] for read-free balanced Y.
    assert _result(f"+[{prefix}[]].") == ("halt", "\x00")
    assert _result("+[].") == ("diverge", "")


def test_cell_preservation_is_the_missing_hypothesis() -> None:
    assert _result("+[>+<[]].") == _result("+[].") == ("diverge", "")
