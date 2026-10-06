r"""Interpreter for Underload.

Parentheses push their contents, ``~:!*a`` transform stack strings, ``^``
splices the top string immediately after itself, and ``S`` outputs one.
Unknown non-whitespace commands, unbalanced parentheses, and stack underflow raise
:class:`~esolangs.exceptions.HaltError`. An empty program is valid.
The spec's ``"`` quoting of ``[]<>"`` is not implemented: the wiki notes
that no known interpreter, the reference included, implements it.
"""

from __future__ import annotations

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

type _State = tuple[str, int, tuple[str, ...]]
type _Effect = str | None


def _fail() -> None:
    raise HaltError(
        "Underload stack underflow",
        hint="leave enough stack entries for the operation to consume",
    )


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
    """Execute one command and return immutable state plus optional output."""
    program, at, packed = state
    if at >= len(program):
        return state, None
    stack = list(packed)
    command = program[at]
    effect = None
    if command.isspace():
        return (program, at + 1, packed), None
    if command == "(":
        value, at = _element(program, at)
        stack.append(value)
        return (program, at, tuple(stack)), None
    if command == ")":
        raise HaltError("unmatched Underload ')'", hint="open the string with '('")
    if command not in "~:!*a^S":
        raise HaltError(
            f"unknown Underload command {command!r}",
            hint="use () strings and ~ : ! * a ^ S commands",
        )
    needed = 2 if command in "~*" else 1
    if len(stack) < needed:
        _fail()
    if command == "~":
        stack[-2:] = stack[-2:][::-1]
    elif command == ":":
        stack.append(stack[-1])
    elif command == "!":
        stack.pop()
    elif command == "*":
        right, left = stack.pop(), stack.pop()
        stack.append(left + right)
    elif command == "a":
        stack[-1] = f"({stack[-1]})"
    elif command == "^":
        program = program[: at + 1] + stack.pop() + program[at + 1 :]
    else:
        effect = stack.pop()
    return (program, at + 1, tuple(stack)), effect


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
        return (*self.state, self.io.position())

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
