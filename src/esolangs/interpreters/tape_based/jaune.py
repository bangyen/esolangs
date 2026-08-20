"""Interpreter for Jaune.

A brainfuck-like cell array with a dedicated "hold" cell.  ``^`` outputs the
current cell as a decimal number, ``v`` reads a digit of input, ``>``/``<``
move the pointer, ``#`` copies the current cell to the hold cell, ``&`` adds
the hold cell to the current cell, ``%`` zeroes it, and ``+``/``-`` with an
optional count adjust it.  ``(number):`` labels a position, ``(number)?``
jumps to it when the current cell is nonzero, ``(number)!`` when it is zero,
``(number)$`` defines a subroutine, ``(number)@`` calls it, ``;`` separates
subroutines, and ``.`` ends the main program.  A bare ``+``/``-`` (no
number) adds/subtracts 1; a repeated command like ``^^`` is a counted
command (repeat 2 times).  ``v`` as a command operand (``v+``) reads an
input digit and uses it as the count.

Documented decisions for gaps in the wiki spec:
- ``^`` prints the current cell as a decimal integer (the compiler's RISC-V
  output routine does the same), not as a byte;
- ``v`` reads one input character and stores ``ord(c) - 48`` (the compiler
  subtracts 48), raising :class:`EOFError` when input runs out;
- the pointer starts at cell 0 and moves into an unbounded array of
  zero-initialized cells; cells hold plain integers with no wrapping (the
  author's reference JauneJS stores each cell as a JavaScript number and
  does plain ``+=``/``-=``, no modulo or bitmask);
- a jump to an undefined label, a call to an undefined subroutine, or a
  ``;`` with no active subroutine call is an invalid runtime operation
  (:class:`~esolangs.exceptions.HaltError`); a command that requires a
  number but has none is malformed (:class:`ValueError`); an infinite loop
  (a jump that never halts) is left to run, bounded by the caller's
  ``timeout``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


@dataclass
class _Command:
    """One parsed Jaune command."""

    op: str
    arg: int | None = None  # the numeric operand, or None for a bare command


def _parse(code: str) -> list[_Command]:
    """Parse a program into commands, expanding counts and number operands."""
    out: list[_Command] = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in "^><#&%.":
            out.append(_Command(c))
            i += 1
        elif c == ";":
            out.append(_Command(";"))
            i += 1
        elif c == "v":
            # 'v' reads a digit; as an operand ('v+') the read value is the count
            if i + 1 < n and code[i + 1] in "+-":
                out.append(_Command("v" + code[i + 1]))
                i += 2
            else:
                out.append(_Command("v"))
                i += 1
        elif c in "+-":
            # a run like ++ is a counted command (repeat); a bare + is +1
            j = i
            while j < n and code[j] == c:
                j += 1
            count = j - i
            out.append(_Command("+" if c == "+" else "-", count))
            i = j
        elif c.isdigit():
            j = i
            while j < n and code[j].isdigit():
                j += 1
            num = int(code[i:j])
            if j < n and code[j] in ":-?!$@":
                out.append(_Command(code[j], num))
                i = j + 1
            elif j < n and code[j] in "+-":
                out.append(_Command("+" if code[j] == "+" else "-", num))
                i = j + 1
            else:
                # a bare number with no operator: ignore (no-op)
                i = j
        elif c in ":-?!$@":
            # a bare operator with no number: malformed
            raise ValueError(f"command {c!r} requires a number")
        else:
            i += 1  # ignore anything else
    return out


class _Machine:
    """One Jaune run: cells, pointer, hold cell, and parsed commands."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.commands = _parse(code)
        self.cells: list[int] = [0]
        self.ptr = 0
        self.hold = 0
        self.pos = 0
        self.call_stack: list[int] = []

    @property
    def halted(self) -> bool:
        return self.pos >= len(self.commands)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.pos,
            tuple(self.cells),
            self.ptr,
            self.hold,
            tuple(self.call_stack),
            self.io.position(),
        )

    def _label(self, num: int) -> int | None:
        """Return the command index of the ``num`` label, or None."""
        for i, cmd in enumerate(self.commands):
            if cmd.op == ":" and cmd.arg == num:
                return i
        return None

    def _subroutine(self, num: int) -> int | None:
        """Return the command index of the ``num`` subroutine, or None."""
        for i, cmd in enumerate(self.commands):
            if cmd.op == "$" and cmd.arg == num:
                return i
        return None

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the position."""
        if self.halted:
            return
        cmd = self.commands[self.pos]
        c = cmd.op

        if c == "^":
            self.io.print_num(self.cells[self.ptr])
        elif c == "v":
            ch = self.io.input_str()
            self.cells[self.ptr] = ord(ch[0]) - 48 if ch else 0
        elif c in ("v+", "v-"):
            ch = self.io.input_str()
            val = ord(ch[0]) - 48 if ch else 0
            self.cells[self.ptr] += val if c == "v+" else -val
        elif c == ">":
            self.ptr += 1
            if self.ptr == len(self.cells):
                self.cells.append(0)
        elif c == "<":
            if self.ptr == 0:
                self.cells.insert(0, 0)
            else:
                self.ptr -= 1
        elif c == "#":
            self.hold = self.cells[self.ptr]
        elif c == "&":
            self.cells[self.ptr] += self.hold
        elif c == "%":
            self.cells[self.ptr] = 0
        elif c == "+":
            self.cells[self.ptr] += cmd.arg or 1
        elif c == "-":
            self.cells[self.ptr] -= cmd.arg or 1
        elif c == ":":
            pass  # a label position; execution falls through
        elif c == "?":
            if cmd.arg is None:  # pragma: no cover - _parse rejects bare operators
                raise HaltError(f"{c} requires a number")
            target = self._label(cmd.arg)
            if target is None:
                raise HaltError(f"jump to undefined label {cmd.arg}")
            if self.cells[self.ptr] != 0:
                self.pos = target
                return
        elif c == "!":
            if cmd.arg is None:  # pragma: no cover - _parse rejects bare operators
                raise HaltError(f"{c} requires a number")
            target = self._label(cmd.arg)
            if target is None:
                raise HaltError(f"jump to undefined label {cmd.arg}")
            if self.cells[self.ptr] == 0:
                self.pos = target
                return
        elif c == "$":
            pass  # a subroutine definition; execution falls through in place
        elif c == "@":
            if cmd.arg is None:  # pragma: no cover - _parse rejects bare operators
                raise HaltError(f"{c} requires a number")
            target = self._subroutine(cmd.arg)
            if target is None:
                raise HaltError(f"call to undefined subroutine {cmd.arg}")
            self.call_stack.append(self.pos + 1)
            self.pos = target
            return
        elif c == ";":
            if not self.call_stack:
                raise HaltError("; with no active subroutine call")
            self.pos = self.call_stack.pop()
            return
        elif c == ".":
            self.pos = len(self.commands)
            return

        self.pos += 1


def run(code: str, io: IO) -> None:
    """Run a Jaune program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
