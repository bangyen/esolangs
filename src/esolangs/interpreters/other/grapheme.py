"""Interpreter for Grapheme.

A Turing-complete stack language whose program text is a series of
independent uppercase Latin letters, each one a command.  The stack holds
unbounded signed integers, strings, and functions; an untyped variable
system maps names (integers or strings) to values.  ``E``/``F``/``H`` toggle
string/int/function mode, in which characters accumulate into a value pushed
when the mode ends (``E``/``F``/``H`` cannot appear inside the value, so
strings are uppercase letters without ``E`` and integers are letter digits).

Decisions for gaps in the wiki spec (documented):
- popping an empty stack, math on a function, ``Y`` on a function, a
  negative integer in ``N`` (whose letter alphabet is only ``A``-``J``),
  a function as a variable name, an undeclared variable in ``D``, and
  division by zero are invalid operations (:class:`~esolangs.exceptions
  .HaltError`), and a character outside ``A``-``Z`` is malformed
  (:class:`ValueError`);
- ``G``/``I``/``Q``/``Z`` run a function in a fresh normal-mode context
  sharing the stack and variables, so a function cannot leave the caller in
  a mid-string/int/function mode;
- ``W`` reads a whole line and raises :class:`EOFError` when input is
  exhausted;
- a function value is the command string between its ``H``s, so ``N`` on a
  function returns exactly that body.
"""

from __future__ import annotations

import sys
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_FUNC = "func"


def _int_from(buf: list[str]) -> int:
    """Parse an intmode buffer: ``res = (res + digit) * 10`` per letter."""
    res = 0
    for c in buf:
        res = (res + (ord(c) - 64 if c != "Z" else 0)) * 10
    return res


def _to_int(value: object) -> int:
    """Convert a value to an integer (the ``J`` command)."""
    if isinstance(value, int):
        return value
    if isinstance(value, tuple):  # function -> number of commands
        return len(value[1])
    if not isinstance(value, str):
        raise AssertionError(f"unexpected value {value!r}")
    res = 0
    for c in value:
        if c == "F":
            break
        res = (res + (ord(c) - 64 if c != "Z" else 0)) * 10
    return res


def _to_str(value: object) -> str:
    """Convert a value to a string (the ``N`` command)."""
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):  # function -> its body
        return cast(str, value[1])
    if not isinstance(value, int):
        raise AssertionError(f"unexpected value {value!r}")
    digits = "JABCDEFGHI"  # J = 0, A = 1, ..., I = 9
    if value == 0:
        return "J"
    res: list[str] = []
    while value:
        res.append(digits[value % 10])
        value //= 10
    return "".join(reversed(res))


def _as_num(value: object) -> int:
    """Math operand: an integer, or the ord of a string's first character."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return ord((value or "\0")[0])
    raise HaltError("math on a function is undefined")


def _truthy(value: object) -> bool:
    """Falsy values are zero, the empty string, and the empty function."""
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value != ""
    if isinstance(value, tuple):
        return cast(str, value[1]) != ""
    raise AssertionError(f"unexpected value {value!r}")


class _Machine:
    """Shared stack, variables, and step counter for one top-level run."""

    def __init__(self, io: IO, limit: int) -> None:
        self.stack: list[object] = []
        self.vars: dict[object, object] = {}
        self.io = io
        self.limit = limit
        self.steps = 0

    def pop(self) -> object:
        if not self.stack:
            raise HaltError("popped an empty stack")
        return self.stack.pop()


def _exec(code: str, machine: _Machine, depth: int) -> None:
    """Run ``code`` in a fresh normal-mode context sharing the machine state."""
    if depth > 500:
        raise HaltError("recursion limit exceeded")
    stack, io = machine.stack, machine.io
    mode = ""
    buf: list[str] = []
    pc = 0
    n = len(code)
    pending_at = -1

    while pc < n:
        machine.steps += 1
        if machine.steps > machine.limit:
            raise HaltError(f"execution exceeded the {machine.limit}-command limit")
        c = code[pc]
        if mode == "string":
            if c == "E":
                mode = ""
                stack.append("".join(buf))
                buf = []
            else:
                buf.append(c)
            pc += 1
            continue
        if mode == "int":
            if c == "F":
                mode = ""
                stack.append(_int_from(buf))
                buf = []
            else:
                buf.append(c)
            pc += 1
            continue
        if mode == "func":
            if c == "H":
                mode = ""
                stack.append((_FUNC, "".join(buf)))
                buf = []
            else:
                buf.append(c)
            pc += 1
            continue

        if c == "A":
            b, a = machine.pop(), machine.pop()
            stack.append(_as_num(a) + _as_num(b))
        elif c == "B":
            b, a = machine.pop(), machine.pop()
            stack.append(_as_num(a) - _as_num(b))
        elif c == "R":
            b, a = machine.pop(), machine.pop()
            if _as_num(b) == 0:
                raise HaltError("division by zero")
            stack.append(_as_num(a) // _as_num(b))
        elif c == "S":
            b, a = machine.pop(), machine.pop()
            stack.append(_as_num(a) * _as_num(b))
        elif c == "C":
            name, value = machine.pop(), machine.pop()
            if isinstance(name, tuple):
                raise HaltError("a function cannot name a variable")
            machine.vars[name] = value
        elif c == "D":
            name = machine.pop()
            if isinstance(name, tuple):
                raise HaltError("a function cannot name a variable")
            try:
                stack.append(machine.vars[name])
            except KeyError:
                raise HaltError(f"undeclared variable {name!r}") from None
        elif c == "E":
            mode, buf = "string", []
        elif c == "F":
            mode, buf = "int", []
        elif c == "G":
            value = machine.pop()
            body = value[1] if isinstance(value, tuple) and value[0] == _FUNC else value
            if not isinstance(body, str):
                raise HaltError("G needs a string or a function")
            _exec(body, machine, depth + 1)
        elif c == "H":
            mode, buf = "func", []
        elif c == "I":
            value = machine.pop()
            if isinstance(value, tuple) and value[0] == _FUNC:
                _exec(value[1], machine, depth + 1)
            else:
                stack.append(value)
        elif c == "J":
            stack.append(_to_int(machine.pop()))
        elif c == "K":
            value = machine.pop()
            stack.append(value)
            stack.append(value)
        elif c == "L":
            a, b = machine.pop(), machine.pop()
            stack.append(a)
            stack.append(b)
        elif c == "M":
            machine.pop()
        elif c == "N":
            stack.append(_to_str(machine.pop()))
        elif c == "O":
            value = machine.pop()
            stack.append(len(value) if isinstance(value, str) else value)
        elif c == "P":
            stack.reverse()
        elif c == "Q":
            a, b = machine.pop(), machine.pop()
            if isinstance(a, tuple) and a[0] == _FUNC and _truthy(b):
                _exec(a[1], machine, depth + 1)
        elif c == "T":
            value = machine.pop()
            stack.append(1 if not _truthy(value) else 0)
        elif c == "U":
            value = machine.pop()
            if not _truthy(value):
                pc += 1
        elif c == "V":
            a, b = machine.pop(), machine.pop()
            if not _truthy(a):
                pc += _to_int(b)
        elif c == "W":
            stack.append(io.input_str())
        elif c == "X":
            value = machine.pop()
            if _truthy(value):
                # execute the next command, then skip the one after it
                pending_at = pc
            else:
                # skip the next command entirely
                pc += 1
        elif c == "Y":
            value = machine.pop()
            if isinstance(value, str):
                io.print_str(value)
            elif isinstance(value, int):
                io.print_value(value)
            else:
                raise HaltError("Y cannot output a function")
        elif c == "Z":
            value = machine.pop()
            if isinstance(value, tuple) and value[0] == _FUNC:
                while stack:
                    _exec(value[1], machine, depth + 1)
        else:
            raise AssertionError(f"unhandled command {c!r}")
        pc += 1
        if pending_at >= 0 and pc == pending_at + 2:
            pc += 1
            pending_at = -1

    if mode == "string":
        stack.append("".join(buf))
    elif mode == "int":
        stack.append(_int_from(buf))
    elif mode == "func":
        stack.append((_FUNC, "".join(buf)))


def run(code: str, io: IO, limit: int = 1_000_000) -> None:
    """Run a Grapheme program, halting after ``limit`` commands."""
    if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in code):
        raise ValueError("Grapheme programs may only contain uppercase Latin letters")
    _exec(code, _Machine(io, limit), 0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
