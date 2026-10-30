"""Interpreter for CARP.

A program is one instruction per line, ``OP rR C`` (``#`` to end of line is
a comment; blank and comment-only lines are skipped; lines are numbered from
1 over the instructions).  Fifteen 4-bit registers ``r1``..``r15`` start at
0.  Jumping to line 0, or past the last line, halts; so does running off the
last line.

Commands:
    ``INC rR C``  at 15 goto C (no wrap); else add one, next line
    ``DEC rR C``  at 0 next line; else subtract one, goto C
    ``CLR rR C``  set to 0, next line (``C`` unused)
    ``OUT rR C``  print the value in decimal, next line (``C`` unused)
    ``INP rR C``  read a decimal integer 0..15 into the register, next line

Input/output:
    ``INP`` reads one whitespace-separated integer; ``OUT`` prints decimal
    digits with no separator.  A read at EOF raises.

Errors:
    ProgramError: a malformed line, an unknown mnemonic, a register outside
        1..15, or a program of only blank and comment lines.
    InputExhaustedError: ``INP`` at EOF.
    ArgumentError: an input token that is not an integer.
    HaltError: ``INP`` of a value outside 0..15.

Decisions:
    * The page's table gives numeric opcodes but its examples and "new
      assembly semantics" are mnemonic; only mnemonics are source (case
      folded, as the example's ``r3`` is lower case).
    * The addition example ends ``DEC r1 0`` and so halts by falling off the
      end when r1 is 0: running past the last line halts.
    * A line number beyond the program halts too; ``CLR``/``OUT``/``INP``
      take a line operand the page requires ("all commands accept and
      require 2 operands") and ignore it.
    * ``INP`` of a value that does not fit a nibble is refused rather than
      truncated.
"""

from __future__ import annotations

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import parse_integer
from esolangs.runtime.source_hints import syntax_error

_OPS = ("INC", "DEC", "CLR", "OUT", "INP")

type _Instr = tuple[str, int, int]
#: ``(pc, registers)``; ``pc`` is a 0-based index, -1 once halted.
type _State = tuple[int, tuple[int, ...]]


def _parse(code: str) -> tuple[_Instr, ...]:
    """Return the instructions as ``(op, register, line)``."""
    program = []
    for text in code.splitlines():
        words = text.split("#", 1)[0].split()
        if not words:
            continue
        hint = "write `OP rR C`, e.g. `INC r1 2`"
        if len(words) != 3:
            raise syntax_error(f"malformed line: {' '.join(words)!r}", hint)
        op, reg, line = words
        op = op.upper()
        if op not in _OPS:
            raise syntax_error(f"unknown command {op!r}", hint)
        if reg[:1] not in "rR" or not reg[1:].isascii() or not reg[1:].isdigit():
            raise syntax_error(f"malformed register {reg!r}", hint)
        r = parse_integer(reg[1:])
        if not 1 <= r <= 15:
            raise syntax_error(f"register r{r} is outside r1..r15", hint)
        if not line.isascii() or not line.isdigit():
            raise syntax_error(f"malformed line number {line!r}", hint)
        program.append((op, r, parse_integer(line)))
    if not program:
        raise syntax_error("a program needs at least one instruction", "add one")
    return tuple(program)


def _advance(
    state: _State, program: tuple[_Instr, ...], byte: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one instruction, and the text to print.

    Pure: ``INP``'s value arrives as ``byte``.
    """
    pc, regs = state
    op, r, line = program[pc]
    value = regs[r - 1]
    out = None
    nxt = pc + 1
    if op == "INC":
        if value == 15:
            nxt = line - 1
        else:
            value += 1
    elif op == "DEC":
        if value:
            value -= 1
            nxt = line - 1
    elif op == "CLR":
        value = 0
    elif op == "OUT":
        out = str(value)
    elif byte is not None:  # INP
        value = byte
    if value != regs[r - 1]:
        regs = (*regs[: r - 1], value, *regs[r:])
    return (nxt if nxt < len(program) else -1, regs), out


class _Machine:
    """The run state: the program counter and fifteen registers."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.program = _parse(code)
        self.io = io
        self.state: _State = (0, (0,) * 15)

    @property
    def halted(self) -> bool:
        return self.state[0] < 0

    @property
    def registers(self) -> tuple[int, ...]:
        """The fifteen register values, ``r1`` first."""
        return self.state[1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Execute one instruction; the shell owns the two ports."""
        if self.halted:
            return
        byte = None
        if self.program[self.state[0]][0] == "INP":
            byte = self.io.input_num()
            if not 0 <= byte <= 15:
                raise HaltError(
                    f"input {byte} does not fit a 4-bit register",
                    hint="supply an integer from 0 to 15",
                )
        self.state, out = _advance(self.state, self.program, byte)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a CARP program to completion."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
