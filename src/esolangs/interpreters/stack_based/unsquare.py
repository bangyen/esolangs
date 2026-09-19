"""Interpreter for Unsquare.

A stack with an accumulator: ``O``/``I`` push 0/1, ``A`` pops into the
accumulator, ``S`` swaps the top two, ``+``/``-``/``x`` add 2, subtract
2, double, ``P`` pushes it, ``o`` prints the top as a character (decimal
if not a code point), ``i`` reads a line (re-prompting on blank) and
pushes its first character, ``>``/``<`` loop unless the accumulator is
0 or 1.  An empty pop, a swap or ``o`` without enough elements, an
unmatched ``<`` or a ``>`` with no ``<`` raise :class:`HaltError` (the
cross-check exits 3); ``i`` raises :class:`EOFError` when exhausted.
:func:`_advance` is pure and total over an immutable ``_State``:
:func:`_needs` lets the shell reject an underflow first and
:func:`_forward` returns ``None`` for an unmatched ``>``.
"""

from __future__ import annotations

import sys
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: The largest value ``o`` can print as a character, and the surrogate range
#: it must not hand to ``chr``.  Anything else prints as a decimal instead.
_MAX_CHAR = 0x10FFFF
_SURROGATES = range(0xD800, 0xE000)

#: How many stack elements each command needs to run.  ``S`` is the only
#: one that needs two; the other two need one.  A command absent from
#: this mapping needs none.
_NEEDS = {"A": 1, "o": 1, "S": 2}


#: One instant of a run: ``(ind, acc, stack, jumps)`` -- the code cursor,
#: the accumulator, the data stack, and the jump-return stack.  A value, not
#: a mutable record: every transition below returns a new one rather than
#: editing one in place, and both stacks are tuples for the same reason.
#:
#: The jump stack is state, not a scratch register: a ``<`` reads the
#: position a matching ``>`` pushed, so two runs sitting on the same command
#: with different jump stacks will go different places next.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
class _State(NamedTuple):
    """One instant of a run."""

    ind: int
    acc: int
    stack: tuple[int, ...]
    jumps: tuple[int, ...]


def _needs(char: str) -> int:
    """Return how many stack elements ``char`` requires to run."""
    return _NEEDS.get(char, 0)


def _forward(code: str, ind: int) -> int | None:
    """Return the position of the ``<`` matching the ``>`` at ``ind``, or ``None``."""
    depth = 1
    while depth:
        ind += 1
        if ind >= len(code):
            return None
        if code[ind] == ">":
            depth += 1
        elif code[ind] == "<":
            depth -= 1
    return ind


def _advance(
    state: _State,
    code: str,
    byte: int | None = None,
    target: int | None = None,
) -> _State:
    """Return the state after executing the command at the cursor.

    ``>`` records ``ind - 1`` so the shared increment leaves the jump stack
    one before the bracket, and ``<`` lands back on it.
    """
    ind, acc, stack, jumps = state
    char = code[ind]
    if char == "O":
        stack = (*stack, 0)
    elif char == "I":
        stack = (*stack, 1)
    elif char == "A":
        acc, stack = stack[-1], stack[:-1]
    elif char == "S":
        stack = (*stack[:-2], stack[-1], stack[-2])
    elif char == "+":
        acc += 2
    elif char == "-":
        acc -= 2
    elif char == "x":
        acc *= 2
    elif char == "P":
        stack = (*stack, acc)
    elif char == "i":
        stack = (*stack, byte if byte is not None else 0)
    elif char == ">":
        # The accumulator decides: 0 or 1 skips the loop, anything else
        # enters it and records where to come back to.
        if acc in (0, 1):
            ind = target if target is not None else ind
        else:
            jumps = (*jumps, ind - 1)
    elif char == "<":
        ind, jumps = jumps[-1], jumps[:-1]
    return _State(ind + 1, acc, stack, jumps)


class _Machine:
    """Per-run Unsquare state: the stack, jump stack, accumulator, cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Start with empty stacks, a zero accumulator, at the first token."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = _State(0, 0, (), ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def acc(self) -> int:
        return self.state[1]

    @property
    def stack(self) -> tuple[int, ...]:
        """The data stack, bottom first."""
        return self.state[2]

    @property
    def jumps(self) -> tuple[int, ...]:
        return self.state[3]

    def load(self, stack: tuple[int, ...]) -> None:
        """Put ``stack`` under the machine without running anything.

        For watching what a short op-string does to a stack with depth.
        """
        ind, acc, _stack, jumps = self.state
        self.state = _State(ind, acc, tuple(stack), jumps)

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: accumulator + loop stack.  ``stack``
    # above already is the view.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The accumulator, the only cell this language addresses."""
        return [self.state[1]]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Both stacks are already tuples, so they go in as they stand, in
        # the order this returned before the fields moved into a state.
        ind, acc, stack, jumps = self.state
        return (ind, acc, stack, jumps, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        I/O and all five error cases are here.  An unmatched ``>`` leaves the
        cursor at the end, so a caller catching the error sees a halted machine.
        """
        if self.halted:
            return
        ind, acc, stack, jumps = self.state
        char = self.code[ind]
        if len(stack) < _needs(char):
            raise HaltError(
                "empty stack" if _needs(char) == 1 else "swap needs two elements"
            )
        if char == "<" and not jumps:
            raise HaltError("unmatched <")
        target = None
        byte = None
        if char == ">" and acc in (0, 1):
            target = _forward(self.code, ind)
            if target is None:
                self.state = _State(self.size, acc, stack, jumps)
                raise HaltError("unmatched >")
        elif char == "o":
            value = stack[-1]
            codepoint = value & 0xFFFFFFFF
            if codepoint <= _MAX_CHAR and codepoint not in _SURROGATES:
                self.io.print_char(chr(codepoint))
            else:
                self.io.print_num(value)
        elif char == "i":
            line = self.io.input_str()
            while not line.strip():
                line = self.io.input_str()
            byte = ord(line[0])
        self.state = _advance(self.state, self.code, byte, target)


def run(code: str, io: IO) -> None:
    """Run an Unsquare program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
