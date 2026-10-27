"""Interpreter for Aprknia.

One stack of unbounded signed integers.  The cursor runs the source left
to right; ``[`` and ``]`` loop while the top is positive, as in
Brainfuck, and every character outside the command set is ignored.

Commands:
    ``*``    pop a, then b; push b+a, b-a, b*a, b/a, b mod a, in that order
    ``1``    push 1
    ``!``    pop
    ``~``    swap the top two
    ``[ ]``  run the body while the top is positive (the test does not pop)
    ``,``    pop a; by a mod 3: 0 pushes an input byte, 1 pops b and prints
             it as a character, 2 prints the top as an integer

Input/output:
    ``,`` reads one byte, or writes one character or one decimal integer.

Errors:
    ProgramError: an unmatched bracket.
    InputExhaustedError: a read at EOF.
    HaltError: a pop, swap or loop test on too short a stack, or printing
    a value outside Unicode as a character.

Decisions:
    * Division truncates toward zero, as the page says, and ``mod`` is the
      remainder that pairs with it (sign of b), so b = a*(b/a) + b mod a.
    * The ``,`` selector takes ``a mod 3`` in the floored sense, so -1
      selects mode 2; the page gives no negative case.
    * "Output current cell" prints the top left after popping a, without
      popping it, and without a newline.
    * A loop test on an empty stack halts with an error rather than
      reading 0: the page gives no empty-stack value anywhere.
"""

from __future__ import annotations

from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: How many values each command needs before it can run.
_NEEDS = {"*": 2, "!": 1, "~": 2, "[": 1, "]": 1, ",": 1}


class _State(NamedTuple):
    """The cursor and the stack, a value rebound per step."""

    ind: int
    stk: tuple[int, ...]


def _brackets(code: str) -> dict[int, int]:
    """Map each bracket to its partner, both ways, rejecting a stray one."""
    table: dict[int, int] = {}
    open_: list[int] = []
    for ind, char in enumerate(code):
        if char == "[":
            open_.append(ind)
        elif char == "]":
            if not open_:
                raise syntax_error("unmatched ']'", "open the loop with [")
            start = open_.pop()
            table[start], table[ind] = ind, start
    if open_:
        raise syntax_error("unmatched '['", "close the loop with ]")
    return table


def _quot(b: int, a: int) -> int:
    """Return b / a truncated toward zero, or 0 for a zero divisor."""
    if not a:
        return 0
    q = abs(b) // abs(a)
    return q if (b < 0) == (a < 0) else -q


def _advance(
    state: _State, code: str, jumps: dict[int, int], byte: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after the command at the cursor, and its output.

    Pure; the shell checked the stack depth and read ``byte``.
    """
    ind, stk = state
    char = code[ind]
    out = None
    if char == "*":
        b, a = stk[-2:]
        q = _quot(b, a)
        stk = (*stk[:-2], b + a, b - a, b * a, q, b - a * q if a else 0)
    elif char == "1":
        stk = (*stk, 1)
    elif char == "!":
        stk = stk[:-1]
    elif char == "~":
        stk = (*stk[:-2], stk[-1], stk[-2])
    elif (char == "[" and stk[-1] <= 0) or (char == "]" and stk[-1] > 0):
        ind = jumps[ind]
    elif char == ",":
        mode, stk = stk[-1] % 3, stk[:-1]
        if mode == 0 and byte is not None:
            stk = (*stk, byte)
        elif mode == 1:
            out, stk = chr(stk[-1]), stk[:-1]
        elif mode == 2:
            out = str(stk[-1])
    return _State(ind + 1, stk), out


class _Machine:
    """An Aprknia run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.jumps = _brackets(code)
        self.state = _State(0, ())

    @property
    def ind(self) -> int:
        return self.state.ind

    @property
    def stack(self) -> list[int]:
        """The stack, bottom first."""
        return list(self.state.stk)

    @property
    def halted(self) -> bool:
        return self.state.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Run one command; the reads, writes and errors happen here."""
        if self.halted:
            return
        ind, stk = self.state
        char = self.code[ind]
        need = _NEEDS.get(char, 0)
        # Modes 1 and 2 of ``,`` read a second value under the selector.
        if char == "," and stk and stk[-1] % 3:
            need = 2
        if len(stk) < need:
            raise HaltError(
                f"{char!r} at position {ind} needs {need} value(s) and the "
                f"stack holds {len(stk)}",
                hint="push enough values before this command",
            )
        if char == "," and stk[-1] % 3 == 1 and not 0 <= stk[-2] <= 0x10FFFF:
            raise HaltError(
                f"',' cannot print {stk[-2]} as a character",
                hint="keep printed values between 0 and 0x10FFFF",
            )
        byte = None
        if char == "," and stk[-1] % 3 == 0:
            byte = self.io.input_char()
        self.state, out = _advance(self.state, self.code, self.jumps, byte)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run an Aprknia program until the cursor passes the end."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
