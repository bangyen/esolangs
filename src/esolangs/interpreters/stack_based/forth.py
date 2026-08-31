"""Interpreter for Forþ.

A stack-based language with a dispatch table of named functions.  Digits
0-9 and A-F push their value, ``:`` duplicates the top, ``+``/``-``/``*``/
``/``/``%`` do arithmetic (the top goes on the right), ``~`` pushes the
bitwise complement of the top, ``.`` prints the top as a character, ``,``
reads a line pushing each byte (rightmost on top), ``(``/``[`` branch or
loop while the top is nonzero, ``{`` stores a scope under the number atop
the stack, ``;`` calls the stored scope, ``o`` reverses the stack, ``c``
rotates the top three, and ``v`` swaps the top two.  Any other character is
ignored.

Semantics:
- arithmetic wraps to signed 32-bit integers, and ``/``/``%`` truncate
  toward zero (C++11 semantics), so negative operands match;
- an empty-stack pop halts the whole program with :class:`HaltError`, while
  the other invalid operations (a binary operator with fewer than two
  values, ``c`` with fewer than three, a division by zero, or an unterminated
  bracket) abort only the innermost scope and are otherwise ignored -- the
  cross-check returns an error code that nested calls discard;
- ``,`` reads a whole line and raises :class:`EOFError` when input runs out
  (like the other stack interpreters), where the cross-check exits with
  status 3;
- ``,`` pushes each character's byte value (the cross-check's signed ``char``
  would push negative values for bytes above 127);
- ``.`` prints the top's low byte (``& 0xFF``),
  rather than the wiki's "print as a unicode character" -- the byte model is
  baked into the arithmetic (``~`` complements, so ``.`` on ``-1`` prints the
  byte 0xFF).

The interpreter runs on a :class:`_Machine` with an explicit call stack (one
frame per active scope), so it is step-capable: ``step()`` executes one
command of the active frame, ``halted`` is true once no frame remains, and a
repeated :meth:`_Machine.snapshot` proves a loop (e.g. a ``[`` loop whose top
never reaches zero).  A scope that aborts on an invalid operation pops back
to its caller, whose ``;``/``(``/``[`` discards the status; a top-level abort
sets ``_Machine.error`` so :func:`run` raises :class:`HaltError`, matching
the original status-returning ``_execute``.
"""

import sys
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def _wrap32(value: int) -> int:
    """Wrap ``value`` to a signed 32-bit integer (C++ ``int`` arithmetic)."""
    return (value + 2**31) % 2**32 - 2**31


def _trunc_div(a: int, b: int) -> int:
    """C++-style integer division, truncating toward zero."""
    return int(a / b)


def _trunc_mod(a: int, b: int) -> int:
    """C++-style remainder (the sign of the dividend)."""
    return a - _trunc_div(a, b) * b


@dataclass
class _Frame:
    """One active scope: its code, cursor, and whether it is a ``[`` loop body."""

    code: str
    pc: int = 0
    loop: bool = False


class _Machine:
    """Per-run Forþ state: the shared stack, scope table, and call stack.

    ``step()`` executes one command of the active frame; ``halted`` is true
    once no frame remains.  A ``[`` loop body re-starts while the stack top is
    nonzero, so a loop that never exhausts its top is a finite-state cycle
    the state-cycle hang detector can prove.  The VM and the hang detector
    expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with the top-level ``code`` as the only frame."""
        self.io = io
        self.stack: list[int] = []
        self.table: dict[int, str] = {}
        self.frames: list[_Frame] = [_Frame(code)]
        self.error = False  # the top-level scope aborted (status 3)

    @property
    def halted(self) -> bool:
        """Whether every scope has completed."""
        return not self.frames

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(self.stack),
            frozenset(self.table.items()),
            tuple((f.code, f.pc, f.loop) for f in self.frames),
            self.io.position(),
        )

    def _top(self) -> int:
        if not self.stack:
            raise HaltError
        return self.stack[-1]

    def _pop(self) -> int:
        value = self._top()
        self.stack.pop()
        return value

    def _finalize_finished(self) -> None:
        """Pop completed frames, re-running a ``[`` loop body while it holds.

        Only the top frame can be finished at a time; a loop body that still
        has a nonzero top starts a fresh pass (finalized by a later step, so
        an empty body is a no-op step whose repeated snapshot proves a hang).
        """
        while self.frames and self.frames[-1].pc >= len(self.frames[-1].code):
            frame = self.frames[-1]
            if frame.loop and self._top() != 0:
                self.frames[-1] = _Frame(frame.code, 0, loop=True)
                return
            self.frames.pop()

    def _abort(self) -> None:
        """Abort the innermost scope on an invalid operation (status 3).

        The abort behaves like the scope completing: a loop body re-checks
        its condition, a nested scope pops back to its caller (which
        discards the status), and a top-level scope halts with ``error``.
        """
        top_level = len(self.frames) == 1
        self.frames[-1].pc = len(self.frames[-1].code)
        self._finalize_finished()
        if top_level:
            self.error = True

    def step(self) -> None:
        """Execute one command of the active frame."""
        if self.halted:
            return
        self._finalize_finished()
        if not self.frames:
            return
        frame = self.frames[-1]
        if frame.pc >= len(frame.code):
            return  # a finished pass (an empty loop body) is a no-op step
        char = frame.code[frame.pc]
        frame.pc += 1

        if "0" <= char <= "9":
            self.stack.append(ord(char) - 48)
        elif "A" <= char <= "F":
            self.stack.append(ord(char) - 55)
        elif char == ":":
            self.stack.append(self._top())
        elif char == "~":
            self.stack.append(~self._pop())
        elif char == ".":
            self.io.print_char(chr(self._pop() & 0xFF))
        elif char == ",":
            for ch in self.io.input_str():
                self.stack.append(ord(ch) & 0xFF)
        elif char == ";":
            scope = self.table.get(self._pop(), "")
            self.frames.append(_Frame(scope))
        elif char == "o":
            self.stack.reverse()
        elif char == "c":
            if len(self.stack) < 3:
                self._abort()
            else:
                self.stack.append(self.stack.pop(-3))
        elif char in "([{":
            add = char
            sub = ")" if char == "(" else "]" if char == "[" else "}"
            start = frame.pc - 1
            match = 1
            while True:
                if frame.pc >= len(frame.code):
                    self._abort()
                    return
                inner = frame.code[frame.pc]
                frame.pc += 1
                if inner == add:
                    match += 1
                elif inner == sub:
                    match -= 1
                if match == 0:
                    break
            scope = frame.code[start + 1 : frame.pc - 1]
            if add == "(":
                if self._top():
                    self.frames.append(_Frame(scope))
            elif add == "[":
                if self._top():
                    self.frames.append(_Frame(scope, 0, loop=True))
            else:
                self.table[self._top()] = scope
        elif char in "+-*/%v":
            if len(self.stack) < 2:
                self._abort()
            else:
                two = self._pop()
                one = self._pop()
                if char == "+":
                    self.stack.append(_wrap32(one + two))
                elif char == "-":
                    self.stack.append(_wrap32(one - two))
                elif char == "*":
                    self.stack.append(_wrap32(one * two))
                elif char == "/":
                    if two == 0:
                        self._abort()
                    else:
                        self.stack.append(_wrap32(_trunc_div(one, two)))
                elif char == "%":
                    if two == 0:
                        self._abort()
                    else:
                        self.stack.append(_wrap32(_trunc_mod(one, two)))
                elif char == "v":
                    self.stack.append(two)
                    self.stack.append(one)


def run(code: str, io: IO) -> None:
    """Run a Forþ program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    if machine.error:
        raise HaltError


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
