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

The interpreter runs on a :class:`_Machine` with an explicit call stack (one
frame per active ``G``/``I``/``Q``/``Z`` call), so it is step-capable:
``step()`` executes one command, ``halted`` is true once no frame remains,
and a repeated :meth:`_Machine.snapshot` proves a loop (e.g. ``Z`` re-running
a function whose net effect on the stack is a no-op).  A program whose stack
keeps growing without repeating a state is not caught this way and needs a
wall-clock bound instead.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
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


@dataclass
class _Frame:
    """One ``_exec`` context: its code, cursor, mode, and pending skip."""

    code: str
    depth: int
    pc: int = 0
    mode: str = ""
    buf: list[str] = field(default_factory=list)
    pending_at: int = -1
    repeat: str = ""  # for ``Z``: re-run this body while the stack is nonempty


class _Machine:
    """Shared stack, variables, step counter, and call stack for a run."""

    def __init__(self, io: IO, limit: int) -> None:
        self.stack: list[object] = []
        self.vars: dict[object, object] = {}
        self.io = io
        self.limit = limit
        self.steps = 0
        self.frames: list[_Frame] = []

    @property
    def halted(self) -> bool:
        return not self.frames

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        ``steps`` is excluded: it only counts toward the execution-limit
        guard and increases every step, so including it would mean no state
        ever repeats and defeat cycle detection entirely.
        """
        return (
            tuple(self.stack),
            frozenset(self.vars.items()),
            tuple(
                (f.code, f.depth, f.pc, f.mode, tuple(f.buf), f.pending_at, f.repeat)
                for f in self.frames
            ),
            self.io.position(),
        )

    def pop(self) -> object:
        if not self.stack:
            raise HaltError("popped an empty stack")
        return self.stack.pop()

    def _flush(self, frame: _Frame) -> None:
        """Push any unterminated mode buffer, as at the end of a program."""
        if frame.mode == "string":
            self.stack.append("".join(frame.buf))
        elif frame.mode == "int":
            self.stack.append(_int_from(frame.buf))
        elif frame.mode == "func":
            self.stack.append((_FUNC, "".join(frame.buf)))
        frame.mode = ""
        frame.buf = []

    def _finish(self, frame: _Frame) -> None:
        """Flush ``frame``'s mode and pop it (or re-run it for ``Z``)."""
        self._flush(frame)
        if frame.repeat and self.stack:
            frame.pc = 0
            frame.pending_at = -1
        else:
            self.frames.pop()

    def step(self) -> None:
        """Execute one command, finishing any frames that are now complete."""
        frame = self.frames[-1]
        if frame.pc >= len(frame.code):
            self._finish(frame)
            return
        self.steps += 1
        if self.steps > self.limit:
            raise HaltError(f"execution exceeded the {self.limit}-command limit")

        stack = self.stack
        code = frame.code
        c = code[frame.pc]

        if frame.mode == "string":
            if c == "E":
                frame.mode = ""
                stack.append("".join(frame.buf))
                frame.buf = []
            else:
                frame.buf.append(c)
            frame.pc += 1
            return
        if frame.mode == "int":
            if c == "F":
                frame.mode = ""
                stack.append(_int_from(frame.buf))
                frame.buf = []
            else:
                frame.buf.append(c)
            frame.pc += 1
            return
        if frame.mode == "func":
            if c == "H":
                frame.mode = ""
                stack.append((_FUNC, "".join(frame.buf)))
                frame.buf = []
            else:
                frame.buf.append(c)
            frame.pc += 1
            return

        body: str | None = None
        repeat = ""
        depth = frame.depth + 1

        if c == "A":
            b, a = self.pop(), self.pop()
            stack.append(_as_num(a) + _as_num(b))
        elif c == "B":
            b, a = self.pop(), self.pop()
            stack.append(_as_num(a) - _as_num(b))
        elif c == "R":
            b, a = self.pop(), self.pop()
            if _as_num(b) == 0:
                raise HaltError("division by zero")
            stack.append(_as_num(a) // _as_num(b))
        elif c == "S":
            b, a = self.pop(), self.pop()
            stack.append(_as_num(a) * _as_num(b))
        elif c == "C":
            name, value = self.pop(), self.pop()
            if isinstance(name, tuple):
                raise HaltError("a function cannot name a variable")
            self.vars[name] = value
        elif c == "D":
            name = self.pop()
            if isinstance(name, tuple):
                raise HaltError("a function cannot name a variable")
            try:
                stack.append(self.vars[name])
            except KeyError:
                raise HaltError(f"undeclared variable {name!r}") from None
        elif c == "E":
            frame.mode, frame.buf = "string", []
        elif c == "F":
            frame.mode, frame.buf = "int", []
        elif c == "G":
            value = self.pop()
            raw = value[1] if isinstance(value, tuple) and value[0] == _FUNC else value
            if not isinstance(raw, str):
                raise HaltError("G needs a string or a function")
            body = raw
        elif c == "H":
            frame.mode, frame.buf = "func", []
        elif c == "I":
            value = self.pop()
            if isinstance(value, tuple) and value[0] == _FUNC:
                body = value[1]
            else:
                stack.append(value)
        elif c == "J":
            stack.append(_to_int(self.pop()))
        elif c == "K":
            value = self.pop()
            stack.append(value)
            stack.append(value)
        elif c == "L":
            a, b = self.pop(), self.pop()
            stack.append(a)
            stack.append(b)
        elif c == "M":
            self.pop()
        elif c == "N":
            stack.append(_to_str(self.pop()))
        elif c == "O":
            value = self.pop()
            stack.append(len(value) if isinstance(value, str) else value)
        elif c == "P":
            stack.reverse()
        elif c == "Q":
            a, b = self.pop(), self.pop()
            if isinstance(a, tuple) and a[0] == _FUNC and _truthy(b):
                body = a[1]
        elif c == "T":
            value = self.pop()
            stack.append(1 if not _truthy(value) else 0)
        elif c == "U":
            value = self.pop()
            if not _truthy(value):
                frame.pc += 1
        elif c == "V":
            a, b = self.pop(), self.pop()
            if not _truthy(a):
                frame.pc += _to_int(b)
        elif c == "W":
            stack.append(self.io.input_str())
        elif c == "X":
            value = self.pop()
            if _truthy(value):
                # execute the next command, then skip the one after it
                frame.pending_at = frame.pc
            else:
                # skip the next command entirely
                frame.pc += 1
        elif c == "Y":
            value = self.pop()
            if isinstance(value, str):
                self.io.print_str(value)
            elif isinstance(value, int):
                self.io.print_value(value)
            else:
                raise HaltError("Y cannot output a function")
        elif c == "Z":
            value = self.pop()
            if isinstance(value, tuple) and value[0] == _FUNC and self.stack:
                body = value[1]
                repeat = value[1]
        else:
            # a string read from input and executed via G/I may carry any
            # character; reject it like the top-level program validation would
            raise ValueError(f"unhandled command {c!r}")

        frame.pc += 1
        if frame.pending_at >= 0 and frame.pc == frame.pending_at + 2:
            frame.pc += 1
            frame.pending_at = -1

        if body is not None:
            if depth > 500:
                raise HaltError("recursion limit exceeded")
            self.frames.append(_Frame(body, depth, repeat=repeat))

        # a command that left the current frame finished (the program ended or
        # a call returned) is completed now, so a caller sees ``halted`` as
        # soon as the last command runs instead of one step later.
        while self.frames and self.frames[-1].pc >= len(self.frames[-1].code):
            self._finish(self.frames[-1])


def run(code: str, io: IO, limit: int = 1_000_000) -> None:
    """Run a Grapheme program, halting after ``limit`` commands."""
    if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in code):
        raise ValueError("Grapheme programs may only contain uppercase Latin letters")
    machine = _Machine(io, limit)
    machine.frames.append(_Frame(code, 0))
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
