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
    """Two stacks with an index choosing the active one."""

    ptr: int = 0
    stk: list[list[int | str]] = field(default_factory=lambda: [[], []])


def run(code: str, io: IO) -> None:
    """Run an Eval program."""
    state = State()

    def top() -> int | str:
        if not state.stk[state.ptr]:
            raise HaltError
        return state.stk[state.ptr][-1]

    def pop() -> int | str:
        if not state.stk[state.ptr]:
            raise HaltError
        return state.stk[state.ptr].pop()

    def bump(delta: int) -> None:
        """Add ``delta`` to the top, halting when the top is not a number."""
        val = pop()
        if not isinstance(val, int):
            raise HaltError
        state.stk[state.ptr].append(val + delta)

    dct: dict[str, Callable[[], object]] = {
        "`": lambda: state.stk[state.ptr].append(1 - state.ptr),
        "^": lambda: state.stk[state.ptr].append(top()),
        "0": lambda: state.stk[state.ptr].append(0),
        "+": lambda: bump(1),
        "-": lambda: bump(-1),
        ".": lambda: io.print_value(pop()),
        "=": lambda: state.stk[1 - state.ptr].append(pop()),
        ";": lambda: pop(),
    }

    def ins(sym: str) -> None:
        ind = 0

        while ind < len(sym):
            if (char := sym[ind]) in dct:
                dct[char]()
            elif char == "~":
                state.ptr ^= 1
            elif char == "*":
                state.stk[state.ptr] = state.stk[state.ptr][::-1]
            elif char == "?":
                if not pop():
                    ind += 1
            elif char == "!":
                val = pop()
                if not isinstance(val, str):
                    raise HaltError
                ins(val)
            elif char in "\"'":
                match = re.match('[^"]*', sym[ind + 1 :])
                s = match[0].replace("`", '"') if match else ""
                ind += len(s) + 1
                if char == "'":
                    s = f'"{s}"'

                state.stk[state.ptr].append(s)

            ind += 1

    ins(code)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
