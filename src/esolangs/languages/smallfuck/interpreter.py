r"""Interpreter for Smallfuck.

The tape starts at zero and has one cell per source character. ``*`` flips a
bit, ``<>`` move, and ``[]`` loop. Moving beyond either end halts.

Input/output:
    No input.  Smallfuck does not define I/O, so this implementation prints
    cell 2 at halt (zero when the source is too short to allocate it).

Errors:
    ProgramError: Unbalanced brackets.
"""

from __future__ import annotations

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.brackets import match_brackets
from esolangs.runtime.io import IO

type _State = tuple[int, int, tuple[int, ...], bool]


def _advance(
    state: _State, code: str, brackets: dict[int, int]
) -> tuple[_State, str | None]:
    """Return the next immutable state and any final tape output."""
    ind, ptr, tape, dumped = state
    if ind >= len(code):
        if not dumped:
            return (ind, ptr, tape, True), str(tape[2] if len(tape) > 2 else 0)
        return state, None
    command = code[ind]
    if command == "*":
        tape = (*tape[:ptr], 1 - tape[ptr], *tape[ptr + 1 :])
    elif command == ">":
        ptr += 1
        if ptr >= len(code):
            ind = len(code)
    elif command == "<":
        if ptr == 0:
            ind = len(code)
        else:
            ptr -= 1
    elif (command == "[" and tape[ptr] == 0) or (command == "]" and tape[ptr] != 0):
        ind = brackets[ind]
    return (ind + (ind < len(code)), ptr, tape, dumped), None


class _Machine:
    """A fixed binary tape and instruction pointer."""

    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = match_brackets(code)
        self.size = len(code)
        self.state: _State = (0, 0, (0,) * self.size, False)

    @property
    def halted(self) -> bool:
        return self.state[0] >= self.size

    @property
    def ip(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def memory(self) -> list[int]:
        return list(self.state[2])

    def snapshot(self) -> tuple[object, ...]:
        ind, ptr, tape, _dumped = self.state
        return (ind, ptr, tape)

    def step(self) -> None:
        self.state, output = _advance(self.state, self.code, self.brackets)
        if output is not None:
            self.io.print_str(output)


def run(code: str, io: IO) -> None:
    """Execute ``code`` and print final cell 2."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
