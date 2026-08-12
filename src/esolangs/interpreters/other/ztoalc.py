"""Interpreter for ZTOALC.

Programs are a list of lines; line 1 holds the initial pointer.  Execution
visits line ``v`` when the Collatz step equals ``v``, halting when the value
reaches 1.  Commands print, jump, assign, add, and subtract using the current
value as an expression.

The wiki allows array elements as general expressions; this interpreter
supports reading and writing ``array[index]`` but not nested or compound
indexing (no arrays-of-arrays).  A command missing a required operand
is a malformed program and is rejected with :class:`ValueError`; referencing
an undefined variable, indexing out of range, or reaching a negative pointer
are invalid operations that halt the program with
:class:`~esolangs.exceptions.HaltError`.
"""

import sys
from dataclasses import dataclass
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


@dataclass
class State:
    """Per-run state for a ZTOALC interpreter."""


def run(code: list[str], io: IO) -> None:
    """Run a ZTOALC program, following the Collatz trajectory of line 1."""
    if not code:
        raise ValueError("ZTOALC program cannot be empty")
    ptr = int(code[0])
    state = State()
    var: dict[str, int | list[int]] = {}

    def val(state: State, exp: str) -> int | list[int]:
        if exp == "input":
            return io.input_char()
        if exp in var:
            return var[exp]
        if exp.isnumeric() or (exp[0] == "-" and exp[1:].isnumeric()):
            return int(exp)
        if exp[0] == "[":
            return [0] * cast(int, val(state, exp[1:-1]))
        arg = exp[:-1].split("[")
        if arg[0] not in var:
            raise HaltError
        arr = var[arg[0]]
        if not isinstance(arr, list):
            raise HaltError
        idx = cast(int, val(state, arg[1]))
        if idx < 0 or idx >= len(arr):
            raise HaltError
        return arr[idx]

    def operand(lst: list[str], n: int) -> str:
        """Return the ``n``-th token of a command, rejecting a missing one."""
        if n >= len(lst):
            raise ValueError("missing operand in " + " ".join(lst))
        return lst[n]

    def store(state: State, lhs: str, value: int | list[int]) -> None:
        """Assign ``value`` to ``lhs`` (a variable or an ``array[index]``)."""
        if "[" in lhs:
            name, idx_exp = lhs[:-1].split("[")
            if name not in var or not isinstance(var[name], list):
                raise HaltError
            arr = cast(list[int], var[name])
            idx = cast(int, val(state, idx_exp))
            if idx < 0 or idx >= len(arr):
                raise HaltError
            # arrays-of-arrays are unsupported (see module docstring), so an
            # array element can only hold a scalar
            arr[idx] = cast(int, value)
        else:
            var[lhs] = value

    while p := ptr - 1:
        if p < 0:
            raise HaltError
        ins = code[p] if p < len(code) else ""
        lst = ins.split()

        if "print" in ins:
            io.print_char(chr(cast(int, val(state, operand(lst, 1)))))
        elif "jump" in ins:
            if val(state, operand(lst, 2)):
                ptr += 1
                continue
        elif " =" in ins:
            store(state, operand(lst, 0), val(state, operand(lst, 2)))
        elif "+" in ins:
            store(
                state,
                operand(lst, 0),
                cast(int, val(state, operand(lst, 0)))
                + cast(int, val(state, operand(lst, 2))),
            )
        elif "-" in ins:
            store(
                state,
                operand(lst, 0),
                cast(int, val(state, operand(lst, 0)))
                - cast(int, val(state, operand(lst, 2))),
            )

        if ptr % 2:
            ptr = 3 * ptr + 1
        else:
            ptr //= 2


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
