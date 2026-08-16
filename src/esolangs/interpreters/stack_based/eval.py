r"""Interpreter for Eval.

Commands manipulate two stacks: 0 pushes 0, \\ pushes the current stack index,
^ duplicates, + and - adjust the top, = moves a value to the other stack, ;
pops, ~ switches stacks, * reverses, ? skips the next command on a zero pop,
and ! evaluates the popped string as a program.

Arithmetic on a non-numeric top, or ``!`` on a non-string value, is an invalid
operation and halts the program with :class:`~esolangs.exceptions.HaltError`.
"""

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


@dataclass
class State:
    """Two stacks with an index choosing the active one, and the code cursor."""

    ptr: int = 0
    stk: list[list[int | str]] = field(default_factory=lambda: [[], []])
    io: IO = field(default_factory=IO)
    sym: str = ""
    ind: int = 0

    @property
    def halted(self) -> bool:
        """Whether the code cursor has run off the program."""
        return self.ind >= len(self.sym)

    def __post_init__(self) -> None:
        """Wire the command dispatch to this state's stacks and I/O."""
        self._dct: dict[str, Callable[[], object]] = {
            "`": lambda: self.stk[self.ptr].append(1 - self.ptr),
            "^": lambda: self.stk[self.ptr].append(self._top()),
            "0": lambda: self.stk[self.ptr].append(0),
            "+": lambda: self._bump(1),
            "-": lambda: self._bump(-1),
            ".": lambda: self.io.print_value(self._pop()),
            "=": lambda: self.stk[1 - self.ptr].append(self._pop()),
            ";": lambda: self._pop(),
        }

    def _top(self) -> int | str:
        if not self.stk[self.ptr]:
            raise HaltError
        return self.stk[self.ptr][-1]

    def _pop(self) -> int | str:
        if not self.stk[self.ptr]:
            raise HaltError
        return self.stk[self.ptr].pop()

    def _bump(self, delta: int) -> None:
        """Add ``delta`` to the top, halting when the top is not a number."""
        val = self._pop()
        if not isinstance(val, int):
            raise HaltError
        self.stk[self.ptr].append(val + delta)

    def _iteration(self, sym: str, ind: int) -> int:
        """Execute one command of ``sym`` at ``ind``, returning the new index."""
        if (char := sym[ind]) in self._dct:
            self._dct[char]()
        elif char == "~":
            self.ptr ^= 1
        elif char == "*":
            self.stk[self.ptr] = self.stk[self.ptr][::-1]
        elif char == "?":
            if not self._pop():
                ind += 1
        elif char == "!":
            val = self._pop()
            if not isinstance(val, str):
                raise HaltError
            self._run(val)
        elif char in "\"'":
            match = re.match('[^"]*', sym[ind + 1 :])
            s = match[0].replace("`", '"') if match else ""
            ind += len(s) + 1
            if char == "'":
                s = f'"{s}"'

            self.stk[self.ptr].append(s)

        return ind + 1

    def _run(self, sym: str) -> None:
        """Run a program to completion (a nested ``!`` evaluation)."""
        ind = 0
        while ind < len(sym):
            ind = self._iteration(sym, ind)

    def step(self) -> None:
        """Execute one command, advancing the code cursor."""
        self.ind = self._iteration(self.sym, self.ind)


def run(code: str, io: IO) -> None:
    """Run an Eval program."""
    state = State(io=io, sym=code)
    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
