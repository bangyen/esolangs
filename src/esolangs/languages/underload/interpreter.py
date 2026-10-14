r"""Interpreter for Underload.

Parentheses push their contents, ``~:!*a`` transform stack strings, ``^``
splices the top string immediately after itself, and ``S`` outputs one.
Unknown non-whitespace commands, unbalanced parentheses, and stack underflow raise
:class:`~esolangs.exceptions.HaltError`. An empty program is valid.
The spec's ``"`` quoting of ``[]<>"`` is not implemented: the wiki notes
that no known interpreter, the reference included, implements it.
"""

from __future__ import annotations

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
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
    *rest, top = stack
    printed = None
    match command:
        case "~":  # swap
            stack = (*rest[:-1], top, rest[-1])
        case ":":  # duplicate
            stack = (*stack, top)
        case "!":  # drop
            stack = tuple(rest)
        case "*":  # concatenate, the lower string first
            stack = (*rest[:-1], rest[-1] + top)
        case "a":  # enclose in parentheses
            stack = (*rest, f"({top})")
        case "^":  # run: splice the string in right after this command
            stack = tuple(rest)
            program = program[: at + 1] + top + program[at + 1 :]
        case _:  # "S": print
            stack, printed = tuple(rest), top
    return (program, at + 1, stack), printed


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

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.progress())

    def step(self) -> None:
        if self.halted:
            return
        self.state, effect = _advance(self.state)
        if effect is not None:
            self.io.print_str(effect)


def run(code: str, io: IO) -> None:
    """Execute an Underload program."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
