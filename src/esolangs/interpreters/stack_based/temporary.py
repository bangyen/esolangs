r"""Interpreter for Temporary.

A single stack with two output modes (numeric/byte).  @ reads a line of input
as byte codes, v pushes an integer, * pushes a string, + duplicates, : loops
while the stack is unchanged, \\ loops while it is nonempty, and a draining
loop prints values while the average of the tail exceeds the head.

As the wiki specifies, every fifteen commands (including comments) the stack
is reset, hence the name "The Temporary Stack".  Duplicating an empty stack,
or squishing a value that is not a valid character in byte mode, is an invalid
operation and halts the program with
:class:`~esolangs.exceptions.HaltError`; a ``:`` with no instruction after it
is a malformed program rejected with :class:`ValueError`.
"""

import secrets
import sys
from dataclasses import dataclass, field

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


@dataclass
class State:
    """Stack, output mode, and counters for a Temporary run."""

    stk: list[int] = field(default_factory=list)
    num: bool = True
    ptr: int = 0
    comm: int = 0


def run(source: str, io: IO) -> None:
    """Run a Temporary program."""
    code = source.split()
    state = State()

    def parse(state: State, char: str) -> None:
        rest = code[state.ptr][1:]

        if char == "@":
            s = io.input_str()
            state.stk.extend(ord(c) for c in s)
        elif char == "v":
            state.stk.append(int(rest))
        elif char == "*":
            state.stk.extend(ord(c) for c in rest)
        elif char in "oO":
            state.num = char == "O"
        elif char == "+":
            if not state.stk:
                raise HaltError
            state.stk.append(state.stk[-1])
        elif char == ":":
            state.ptr += 1
            if state.ptr >= len(code):
                raise ValueError("':' requires a following instruction")
            n = len(state.stk)
            while len(state.stk) == n:
                parse(state, code[state.ptr][0])
        elif char == "\\":
            state.ptr += 1
            while len(state.stk):
                parse(state, code[state.ptr][0])
        elif char == "€":
            parse(state, secrets.choice("@v*oO+:\\"))

        while state.stk and sum(state.stk[1:]) / 2 > state.stk[0]:
            n = state.stk.pop(0) - 1
            if not state.num and not 0 <= n <= 0x10FFFF:
                raise HaltError
            io.print_value(n if state.num else chr(n))

        state.comm += 1
        if state.comm % 15 == 0:
            state.stk = []

    while state.ptr < len(code):
        parse(state, code[state.ptr][0])
        state.ptr += 1


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        data = f.read()

    run(data, IO())
