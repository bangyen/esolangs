r"""Interpreter for Smallfuck.

The tape starts at zero and has one cell per source character. ``*`` flips a
bit, ``<>`` move, and ``[]`` loop. Moving beyond either end halts. Smallfuck
does not define I/O, so this implementation prints cell 2 at halt (zero when
the source is too short to allocate it).
"""

from __future__ import annotations

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.brackets import match_brackets
from esolangs.interpreters.io import IO

type _State = tuple[int, int, tuple[int, ...], bool]


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
        ind, ptr, tape, dumped = self.state
        if ind >= self.size:
            if not dumped:
                self.io.print_str(str(tape[2] if len(tape) > 2 else 0))
                self.state = (ind, ptr, tape, True)
            return
        command = self.code[ind]
        if command == "*":
            tape = (*tape[:ptr], 1 - tape[ptr], *tape[ptr + 1 :])
        elif command == ">":
            ptr += 1
            if ptr >= self.size:
                ind = self.size
        elif command == "<":
            if ptr == 0:
                ind = self.size
            else:
                ptr -= 1
        elif (command == "[" and tape[ptr] == 0) or (command == "]" and tape[ptr] != 0):
            ind = self.brackets[ind]
        self.state = (ind + (ind < self.size), ptr, tape, dumped)


def run(code: str, io: IO) -> None:
    """Execute ``code`` and print final cell 2."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
