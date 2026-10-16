"""Interpreter for Ascenic.

Each line is ``A`` repeated opcode times, then ``s`` repeated argument
times; arguments must rise strictly from line to line.  The stack holds
unbounded integers and reads as 0 when empty, so a command on the top of
an empty stack works on a fresh 0.  Lines run in order, and a jump moves
``arg`` lines from the jump; running past the last line halts.  Since line
``i`` (from 0) has an argument above ``i``, a taken ``JMPB`` always lands
before the first line, so every run halts within its line count.  The
wiki's Hello world and A+B run as stated.

Commands:
    0 NOP, 1 PRINT, 2 INPUT, 3 PUSH ``arg``, 4-8 ADD/SUB/MUL/DIV/MOD the
    top by ``arg``, 9 SWAP, 10 POP, 11 JMPB and 12 JMPF when the top is
    nonzero, 13 LT pushes ``top < arg``, 14 TL pushes ``top < second``,
    15 RND pushes 0 or 1, 16-19 ADDS/SUBS/MULS/DIVS pop ``a`` then ``b``
    and push ``a + b``, ``b - a``, ``a * b``, ``b // a``.

Input/output:
    ``INPUT`` with an even argument reads one character's code point, with
    an odd one a whitespace-delimited integer.  ``PRINT`` with an even
    argument writes the top as a character, with an odd one as a decimal
    integer.  ``RND`` draws through the randomness hook, so
    ``esolangs.run(..., seed=s)`` is reproducible.

Errors:
    ProgramError: A line that is not ``A*s+``; an opcode above 19; an
        argument no greater than the line before's.
    InputExhaustedError: ``INPUT`` at EOF.
    ArgumentError: An odd-argument ``INPUT`` given a non-integer token.
    HaltError: A taken ``JMPB``; ``PRINT`` as a character of a value that
        is no code point.

Decisions:
    * A command on an empty stack's top writes it: the wiki's Hello world
      starts ``SUB 1`` then ``ADD 73`` for ``H`` on an empty stack.
    * ``JMPF``/``JMPB`` land ``arg`` lines from the jump, so ``JMPF 1`` is
      the next line; the wiki gives no jumping example.
    * A taken ``JMPB`` raises rather than halting: no line lies there.
    * ``LT`` and ``TL`` push their flag and pop nothing ("push 1 if ...").
    * ``DIV``/``DIVS`` floor and ``MOD`` takes the divisor's sign, as the
      floor division the page names; dividing by 0 gives 0.
    * Blank lines are skipped; carriage returns and surrounding spaces are
      ignored.
"""

from __future__ import annotations

import re
import sys
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Randomness, draw

_LINE = re.compile(r"(A*)(s+)")
_OPCODES = 20
_PRINT, _INPUT, _RND = 1, 2, 15

#: ``(opcode, argument, source line)`` per instruction.
type _Op = tuple[int, int, int]
#: A persistent stack, top first: ``(top, rest)`` cells ending in ``None``.
type _Stack = tuple[int, _Stack] | None
#: ``(next instruction, stack)``.
type _State = tuple[int, _Stack]


def parse(code: str) -> tuple[_Op, ...]:
    """Return the instructions; a malformed line raises ``ValueError``."""
    ops: list[_Op] = []
    for number, line in enumerate(code.split("\n")):
        text = line.strip()
        if not text:
            continue
        match = _LINE.fullmatch(text)
        if match is None:
            raise ValueError(f"Ascenic: line {number + 1} is not A*s+: {text[:20]!r}")
        opcode, arg = len(match[1]), len(match[2])
        if opcode >= _OPCODES:
            raise ValueError(f"Ascenic: line {number + 1} has opcode {opcode} > 19")
        if ops and arg <= ops[-1][1]:
            raise ValueError(
                f"Ascenic: line {number + 1}'s argument {arg} does not "
                f"exceed {ops[-1][1]}"
            )
        ops.append((opcode, arg, number))
    return tuple(ops)


def _pop(stack: _Stack) -> tuple[int, _Stack]:
    """The top and the rest; an empty stack yields 0 and stays empty."""
    return stack if stack is not None else (0, None)


def _advance(
    state: _State, ops: tuple[_Op, ...], value: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one line, and the text it prints.

    Pure: the value ``INPUT`` read or ``RND`` drew arrives as ``value``.
    """
    index, stack = state
    opcode, arg, line = ops[index]
    nxt = index + 1
    out = None
    top, rest = _pop(stack)
    if opcode == _PRINT:
        if arg % 2:
            out = str(top)
        elif 0 <= top <= sys.maxunicode and not 0xD800 <= top <= 0xDFFF:
            out = chr(top)
        else:
            raise HaltError(f"Ascenic: PRINT of {top}, which is no code point")
    elif opcode in {_INPUT, _RND}:
        assert value is not None
        stack = (value, stack)
    elif opcode == 3:
        stack = (arg, stack)
    elif 4 <= opcode <= 8:
        result = (top + arg, top - arg, top * arg, top // arg, top % arg)[opcode - 4]
        stack = (result, rest)
    elif opcode == 9:
        second, below = _pop(rest)
        stack = (second, (top, below))
    elif opcode == 10:
        stack = rest
    elif opcode in {11, 12} and top:
        if opcode == 11:
            raise HaltError(
                f"Ascenic: JMPB {arg} on line {line + 1} lands before the first line"
            )
        nxt = index + arg
    elif opcode == 13:
        stack = (int(top < arg), stack)
    elif opcode == 14:
        stack = (int(top < _pop(rest)[0]), stack)
    elif opcode >= 16:
        b, below = _pop(rest)
        a = top
        result = (a + b, b - a, a * b, b // a if a else 0)[opcode - 16]
        stack = (result, below)
    return (nxt, stack), out


class _Machine:
    """The run state: the next instruction and the stack."""

    reproducible_seed = 0
    ip_shape = "line"

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        self.io = io
        self._rng = rng
        self.ops = parse(code)
        self.state: _State = (0, None)

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.ops)

    @property
    def ip(self) -> tuple[int]:
        """The next instruction's source line, from 0; the line count once halted."""
        if self.halted:
            return (self.ops[-1][2] + 1 if self.ops else 0,)
        return (self.ops[self.state[0]][2],)

    @property
    def stack(self) -> list[object]:
        """The stack, bottom first."""
        values: list[object] = []
        cell = self.state[1]
        while cell is not None:
            values.append(cell[0])
            cell = cell[1]
        return values[::-1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def branching_snapshot(self) -> tuple[object, ...]:
        """Return the current state as a branching search's starting point."""
        return self.state

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has run past the last line."""
        return cast(_State, state)[0] >= len(self.ops)

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_State, ...] | None:
        """Return both draws at ``RND``, ``None`` at ``INPUT``, else the one step.

        ``INPUT`` would need a cursor per branch, so the caller reports
        undecided; printing changes no state.
        """
        current = cast(_State, state)
        if current[0] >= len(self.ops):
            return (current,)
        opcode = self.ops[current[0]][0]
        if opcode == _INPUT:
            return None
        values = (0, 1) if opcode == _RND else (None,)
        return tuple(_advance(current, self.ops, value)[0] for value in values)

    def step(self) -> None:
        """Run one line, reading or drawing first when it needs a value."""
        if self.halted:
            return
        opcode, arg, _ = self.ops[self.state[0]]
        value = None
        if opcode == _INPUT:
            value = self.io.input_num() if arg % 2 else self.io.input_char()
        elif opcode == _RND:
            value = draw(self._rng, 2)
        self.state, out = _advance(self.state, self.ops, value)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Run an Ascenic program."""
    drive(_Machine(code, io, rng))


if __name__ == "__main__":
    script_main(run)
