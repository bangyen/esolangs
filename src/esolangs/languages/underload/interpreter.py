r"""Interpreter for Underload.

Parentheses push their contents, ``~:!*a`` transform stack strings, ``^``
splices the top string immediately after itself, and ``S`` outputs one.
An empty program is valid.

Errors:
    HaltError: an unknown non-whitespace command; unbalanced parentheses;
        stack underflow.

Decisions:
    * The spec's ``"`` quoting of ``[]<>"`` is not implemented: the wiki
      notes that no known interpreter, the reference included, implements it.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.languages.underload.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO

type _State = tuple[str, int, tuple[str, ...]]
type _Effect = str | None


def _element(program: str, start: int) -> tuple[str, int]:
    """Return a parenthesized element's contents and following offset."""
    depth = 1
    at = start + 1
    while at < len(program) and depth:
        if program[at] == "(":
            depth += 1
        elif program[at] == ")":
            depth -= 1
        at += 1
    if depth:
        raise HaltError("unmatched Underload '('", hint="close the string with ')'")
    return program[start + 1 : at - 1], at


def _advance(state: _State) -> tuple[_State, _Effect]:
    """Execute one command; return the next state and any string printed."""
    program, at, stack = state
    if at >= len(program):
        return state, None
    command = program[at]
    if command.isspace():
        return (program, at + 1, stack), None
    if command == "(":
        value, after = _element(program, at)
        return (program, after, (*stack, value)), None
    if command == ")":
        raise HaltError("unmatched Underload ')'", hint="open the string with '('")
    if command not in "~:!*a^S":
        raise HaltError(
            f"unknown Underload command {command!r}",
            hint="use () strings and ~ : ! * a ^ S commands",
        )
    if len(stack) < (2 if command in "~*" else 1):
        raise HaltError(
            "Underload stack underflow",
            hint="leave enough stack entries for the operation to consume",
        )
    rest, top = stack[:-1], stack[-1]
    printed = None
    match command:
        case "~":  # swap
            stack = (*rest[:-1], top, rest[-1])
        case ":":  # duplicate
            stack = (*stack, top)
        case "!":  # drop
            stack = rest
        case "*":  # concatenate, the lower string first
            stack = (*rest[:-1], rest[-1] + top)
        case "a":  # enclose in parentheses
            stack = (*rest, f"({top})")
        case "^":  # run: splice the string in right after this command
            stack = rest
            program = program[: at + 1] + top + program[at + 1 :]
        case _:  # "S": print
            stack, printed = rest, top
    return (program, at + 1, stack), printed


_WORKSPACE_MODEL = WorkspaceModel(
    "underload-v1", ("program", "instruction", "stack", "input_cursor")
)


class _Machine:
    """Underload's growing program and string stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.state: _State = (code, 0, ())

    @property
    def halted(self) -> bool:
        return self.state[1] >= len(self.state[0])

    @property
    def ip(self) -> int:
        return self.state[1]

    @property
    def stack(self) -> list[object]:
        return list(self.state[2])

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of storage and cycle grouping."""
        return _WORKSPACE_MODEL.capture(
            program=self.state[0],
            instruction=self.state[1],
            stack=self.state[2],
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.progress())

    def step(self) -> None:
        if self.halted:
            return
        self.state, effect = _advance(self.state)
        if effect is not None:
            self.io.print_str(effect)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Bind source; each IO-bound construction owns fresh runtime state."""
    if not isinstance(source, str):
        raise TypeError("underload machines require text source")
    if options:
        raise TypeError("underload machines accept no runtime options")

    return RuntimePlan(partial(_Machine, source), partial(_execute, source))


def _execute(code: str, io: IO) -> CompletionReport:
    """Execute an Underload program."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Execute an Underload program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
