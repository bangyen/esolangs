"""Interpreter for Nope.

Every source, including empty source, prints exactly "Nope." and halts.
No parsing or input is performed; no newline is appended.  No error arises
under the constant-language semantics.
"""

from collections.abc import Mapping
from functools import partial
from typing import Any

from esolangs.languages.nope.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO

type _State = bool

_WORKSPACE_MODEL = WorkspaceModel("nope-v1", ("emitted", "input_cursor"))


def _advance(state: _State) -> tuple[_State, str | None]:
    return True, None if state else "Nope."


class _Machine:
    """One constant-output transition, independent of source."""

    def __init__(self, code: str, io: IO) -> None:  # noqa: ARG002 - source is ignored
        self.io = io
        self.state: _State = False

    @property
    def halted(self) -> bool:
        return self.state

    @property
    def ip(self) -> int:
        return int(self.state)

    def snapshot(self) -> tuple[object, ...]:
        return (self.state, self.io.progress())

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture named semantic fields independently of cycle grouping."""
        return _WORKSPACE_MODEL.capture(
            emitted=self.state, input_cursor=self.io.progress()
        )

    def step(self) -> None:
        self.state, output = _advance(self.state)
        if output is not None:
            self.io.print_str(output)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Bind fresh machines; nope has no runtime options."""
    if not isinstance(source, str):
        raise TypeError("nope machines require text source")
    if options:
        raise TypeError("nope machines accept no runtime options")
    return _PLAN


def _execute(code: str, io: IO) -> CompletionReport:
    """Print the constant answer once."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


# Source is ignored, so every preparation can reuse the same factories.
_PLAN = RuntimePlan(partial(_Machine, ""), partial(_execute, ""))


def run(code: str, io: IO) -> None:
    """Print the constant answer once."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
