r"""Interpreter for The Temporary Stack.

A single stack with two output modes (numeric/byte).  @ reads a line of input
as byte codes, v pushes an integer, * pushes a string, + duplicates, : loops
while the stack is unchanged, \\ loops while it is nonempty, and a draining
loop prints values while the average of the tail exceeds the head.

As the wiki specifies, every fifteen commands (including comments) the stack
is reset, hence the name "The The Temporary Stack Stack".  Duplicating an empty stack,
or squishing a value that is not a valid character in byte mode, is an invalid
operation and halts the program with
:class:`~esolangs.exceptions.HaltError`; a ``:`` with no instruction after it
is a malformed program rejected with :class:`ValueError`.
"""

import re
import secrets
import sys
from dataclasses import dataclass, field

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The command characters; every other character is a comment.  A word's
# command is its first command character, so comments may appear inside a
# command (e.g. ``cOOde`` is ``O`` and ``hv1no2th3ing`` pushes 123).
_COMMANDS = r"[@v*oO+:\#€\\]"


@dataclass
class State:
    """Stack, output mode, and counters for a The Temporary Stack run."""

    stk: list[int] = field(default_factory=list)
    num: bool = True
    ptr: int = 0
    comm: int = 0


def run(source: str, io: IO) -> None:
    """Run a The Temporary Stack program."""
    code = source.split()
    state = State()

    def execute(state: State, char: str, rest: str) -> None:
        if char == "@":
            s = io.input_str()
            state.stk.extend(ord(c) for c in s)
        elif char == "v":
            state.stk.append(int(re.sub(r"\D", "", rest)))
        elif char == "*":
            state.stk.extend(ord(c) for c in rest)
        elif char in "oO":
            state.num = char == "O"
        elif char == "+":
            if not state.stk:
                raise HaltError
            state.stk.append(state.stk[-1])
        elif char == "€":
            execute(state, secrets.choice("@v*oO+"), rest)
        # ':', '\\', and '#' fall through: ':'/'\\' are handled in parse
        # because they recurse over the source, and '#' is a no-op comment

    def parse(state: State) -> None:
        word = code[state.ptr]
        m = re.search(_COMMANDS, word)
        if m:
            char = m.group(0)
            rest = word[m.end() :]
        else:
            char = ""
            rest = ""

        if char == ":":
            state.ptr += 1
            if state.ptr >= len(code):
                raise ValueError("':' requires a following instruction")
            n = len(state.stk)
            while len(state.stk) == n:
                parse(state)
        elif char == "\\":
            state.ptr += 1
            while len(state.stk):
                parse(state)
        else:
            execute(state, char, rest)

        while state.stk and sum(state.stk[1:]) / 2 > state.stk[0]:
            n = state.stk.pop(0) - 1
            if not state.num and not 0 <= n <= 0x10FFFF:
                raise HaltError
            io.print_value(n if state.num else chr(n))

        state.comm += 1
        if state.comm % 15 == 0:
            state.stk = []

    while state.ptr < len(code):
        parse(state)
        state.ptr += 1


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        data = f.read()

    run(data, IO())
