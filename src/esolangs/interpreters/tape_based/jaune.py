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
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The two command shapes, kept apart by their operators.  Because no
# operator appears in both, comparing ``cmd.op`` discriminates the union:
# inside ``cmd.op == "?"`` the checker knows the command is a _Numbered and
# that its ``arg`` is an ``int``, so the jumps and the call read the operand
# without testing what :func:`_parse` has already guaranteed.
_CountedOp = Literal["^", "v", "v+", "v-", ">", "<", "#", "&", "%", "+", "-", ";", "."]
_NumberedOp = Literal[":", "?", "!", "$", "@"]

# Spelling the alphabets as typed containers rather than plain strings is
# what lets ``in`` narrow a parsed character to its operator type, so the
# constructors below take it directly instead of casting.
_BARE: frozenset[_CountedOp] = frozenset(("^", ">", "<", "#", "&", "%", "."))
_NUMBERED: frozenset[_NumberedOp] = frozenset((":", "?", "!", "$", "@"))
_READ_OPERAND: dict[str, _CountedOp] = {"+": "v+", "-": "v-"}


@dataclass
class _Counted:
    """A Jaune command with no operand, or with a repeat count.

    ``arg`` is the count where the op takes one (``+``/``-``) and ``None``
    for the bare commands, both of which are legal spellings.
    """

    op: _CountedOp
    arg: int | None = None


@dataclass
class _Numbered:
    """A Jaune command whose operator requires a number: ``:?!$@``.

    :func:`_parse` raises on a bare one of these, so the operand is always
    present by the time the machine dispatches -- which is why ``arg`` is a
    plain ``int`` rather than an optional one.
    """

    op: _NumberedOp
    arg: int


_Command = _Counted | _Numbered


def _parse(code: str) -> list[_Command]:
    """Parse a program into commands, expanding counts and number operands."""
    out: list[_Command] = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in _BARE:
            out.append(_Counted(c))
            i += 1
        elif c == ";":
            out.append(_Counted(";"))
            i += 1
        elif c == "v":
            # 'v' reads a digit; as an operand ('v+') the read value is the count
            if i + 1 < n and (read := _READ_OPERAND.get(code[i + 1])) is not None:
                out.append(_Counted(read))
                i += 2
            else:
                out.append(_Counted("v"))
                i += 1
        elif c in "+-":
            # a run like ++ is a counted command (repeat); a bare + is +1
            j = i
            while j < n and code[j] == c:
                j += 1
            count = j - i
            out.append(_Counted("+" if c == "+" else "-", count))
            i = j
        elif c.isdigit():
            j = i
            while j < n and code[j].isdigit():
                j += 1
            num = int(code[i:j])
            if j < n and (op := code[j]) in _NUMBERED:
                out.append(_Numbered(op, num))
                i = j + 1
            elif j < n and code[j] in "+-":
                # "-" reaches here as a counted subtract, never as a jump:
                # the numbered operators above do not include it.
                out.append(_Counted("+" if code[j] == "+" else "-", num))
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


#: One instant of a run: ``(cells, ptr, hold, pos, calls)`` -- the tape,
#: the cell pointer, the ``#`` hold register, the command cursor, and the
#: stack of return positions.
#:
#: The commands and the label and subroutine tables stay out: Jaune parses
#: its program once and never rewrites it, so a step is handed them rather
#: than carrying them.
type _State = tuple[tuple[int, ...], int, int, int, tuple[int, ...]]


def _set(cells: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    """Return ``cells`` with the cell at ``ptr`` set to ``value``."""
    return (*cells[:ptr], value, *cells[ptr + 1 :])


def _find(commands: Sequence[_Command], op: str, num: int | None) -> int | None:
    """Return the index of the ``op`` marker whose argument is ``num``."""
    for i, cmd in enumerate(commands):
        if cmd.op == op and cmd.arg == num:
            return i
    return None


def _advance(
    state: _State,
    commands: Sequence[_Command],
    value: int | None = None,
) -> _State:
    """Return the state after executing ``cmd``.

    Pure: it reads ``state`` and returns a new one.  ``^``'s printing is
    the caller's business -- the cell it prints is carried forward
    unchanged -- and the three reading forms arrive as ``value``, already
    taken from the port and already converted from its digit.

    The tape grows at both ends: ``>`` past the right edge appends a cell,
    while ``<`` at the left inserts one and leaves the pointer where it is,
    so the new cell becomes cell zero.

    A jump that is taken, a call, and a return all set the cursor outright
    rather than stepping it, which is why each returns early.
    """
    cells, ptr, hold, pos, calls = state
    cmd = commands[pos]
    c = cmd.op

    if c == "^":
        pass  # printed by the caller; the cell is unchanged
    elif c == "v":
        cells = _set(cells, ptr, value if value is not None else 0)
    elif c in ("v+", "v-"):
        val = value if value is not None else 0
        cells = _set(cells, ptr, cells[ptr] + (val if c == "v+" else -val))
    elif c == ">":
        ptr += 1
        if ptr == len(cells):
            cells = (*cells, 0)
    elif c == "<":
        if ptr == 0:
            cells = (0, *cells)
        else:
            ptr -= 1
    elif c == "#":
        hold = cells[ptr]
    elif c == "&":
        cells = _set(cells, ptr, cells[ptr] + hold)
    elif c == "%":
        cells = _set(cells, ptr, 0)
    elif c == "+":
        cells = _set(cells, ptr, cells[ptr] + (cmd.arg or 1))
    elif c == "-":
        cells = _set(cells, ptr, cells[ptr] - (cmd.arg or 1))
    elif c == "?":
        target = _find(commands, ":", cmd.arg)
        if target is None:
            raise HaltError(f"jump to undefined label {cmd.arg}")
        if cells[ptr] != 0:
            return (cells, ptr, hold, target, calls)
    elif c == "!":
        target = _find(commands, ":", cmd.arg)
        if target is None:
            raise HaltError(f"jump to undefined label {cmd.arg}")
        if cells[ptr] == 0:
            return (cells, ptr, hold, target, calls)
    elif c == "@":
        target = _find(commands, "$", cmd.arg)
        if target is None:
            raise HaltError(f"call to undefined subroutine {cmd.arg}")
        return (cells, ptr, hold, target, (*calls, pos + 1))
    elif c == ";":
        if not calls:
            raise HaltError("; with no active subroutine call")
        return (cells, ptr, hold, calls[-1], calls[:-1])
    elif c == ".":
        return (cells, ptr, hold, len(commands), calls)
    # ":" and "$" are positions rather than commands -- a label and a
    # subroutine definition -- so execution falls through them in place.

    return (cells, ptr, hold, pos + 1, calls)


class _Machine:
    """One Jaune run: cells, pointer, hold cell, and parsed commands."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.commands = _parse(code)
        self.cells: tuple[int, ...] = (0,)
        self.ptr = 0
        self.hold = 0
        self.pos = 0
        self.call_stack: tuple[int, ...] = ()

    @property
    def halted(self) -> bool:
        return self.pos >= len(self.commands)

    # The VM's language-shaped view: Cell tape + hold register; ip the command position.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.pos

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.cells)

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.call_stack)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.pos,
            self.cells,
            self.ptr,
            self.hold,
            self.call_stack,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (
            self.cells,
            self.ptr,
            self.hold,
            self.pos,
            self.call_stack,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- ``snapshot`` reads
        all five -- so they stay; the one assignment a step makes is here
        rather than in the rules above.
        """
        self.cells, self.ptr, self.hold, self.pos, self.call_stack = state

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the position.

        The ports live here rather than in the transition: this is the
        shell.  ``^`` prints the cell the transition carries forward
        unchanged, and the three reading forms take a line here and convert
        it from its digit before handing the value over -- an empty line
        reads as zero, which is the language's own rule rather than a
        default the transition invents.
        """
        if self.halted:
            return
        cmd = self.commands[self.pos]

        value = None
        if cmd.op == "^":
            self.io.print_num(self.cells[self.ptr])
        elif cmd.op in ("v", "v+", "v-"):
            ch = self.io.input_str()
            value = ord(ch[0]) - 48 if ch else 0

        self._restore(_advance(self._state, self.commands, value))


def run(code: str, io: IO) -> None:
    """Run a Jaune program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
