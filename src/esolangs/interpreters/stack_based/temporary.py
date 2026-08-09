r"""Interpreter for Temporary.

A single stack with two output modes (numeric/byte).  @ reads a line of input
as byte codes, v pushes an integer, * pushes a string, + duplicates, : loops
while the stack is unchanged, \\ loops while it is nonempty, and a draining
loop prints values while the average of the tail exceeds the head.
"""

import secrets
import sys
from dataclasses import dataclass, field

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
            state.stk.append(state.stk[-1])
        elif char == ":":
            state.ptr += 1
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
