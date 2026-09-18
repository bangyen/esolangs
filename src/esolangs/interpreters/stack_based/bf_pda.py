"""Interpreter for BF-PDA.

A brainfuck variant over a stack of bits whose top is the current cell:
``@`` flips the top, ``.`` prints it, ``<`` pushes a zero, ``>`` pops,
``[``/``]`` loop while the top is 1.  Per the wiki an empty stack reads
as zero for every peek and pop, so every command is defined on every
state and the transition is total; an empty or unbalanced program raises
:class:`ValueError` at load.  A run halts at the end of the code.
:func:`_advance` is pure over an immutable ``_State``; ``.`` is the shell's.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.brackets import match_brackets
from esolangs.interpreters.io import IO

#: ``(ip, stack)``: an immutable value, rebound per step, and exactly what
#: ``snapshot`` returns.  The code is a parameter, not a field.
type _State = tuple[int, tuple[int, ...]]


def _top(stack: tuple[int, ...]) -> int:
    """Return the top bit, or zero for an empty stack."""
    return stack[-1] if stack else 0


def _advance(state: _State, code: str, jumps: dict[int, int]) -> _State:
    """Return the state after executing the command at the cursor.

    ``jumps`` pairs the brackets, matched once at load (both used to scan
    per jump).  Every command sets the cursor itself, since the brackets
    jump past their partner.
    """
    ip, stack = state
    if code[ip] == "@":
        # Empty stack: push the zero the peek saw, then flip it.
        stack = (*stack[:-1], stack[-1] ^ 1) if stack else (1,)
    elif code[ip] == "<":
        stack = (*stack, 0)
    elif code[ip] == ">":
        # Empty stack pops nothing.
        stack = stack[:-1]
    elif code[ip] == "[":
        if _top(stack) == 0:
            return (jumps[ip] + 1, stack)
    elif code[ip] == "]" and _top(stack) == 1:
        return (jumps[ip] + 1, stack)
    return (ip + 1, stack)


class _Machine:
    """Per-run BF-PDA state: the code, the bit stack, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Validate ``code``'s brackets and start with an empty stack."""
        if not code:
            raise ValueError("BF-PDA program cannot be empty")
        # One walk for balance and the jump table (this used to rescan per
        # jump).  An unmatched ``[`` is reported at the innermost waiting
        # one; the old ``rfind`` named a matched bracket in ``[[]``.
        self.jumps = match_brackets(code)

        self.io = io
        self.code = code
        # ``halted`` is read twice per command; take the length once.
        self.size = len(code)
        self.state: _State = (0, ())

    # Views on the state.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def stack(self) -> tuple[int, ...]:
        """The bit stack, bottom first."""
        return self.state[1]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # VM view: the store is the stack, so ``memory`` is empty.

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The state is already the hashable (ip, stack) pair.
        return self.state

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor.

        ``.`` is here, through :func:`_top`.
        """
        if self.halted:
            return
        ip, stack = self.state
        if self.code[ip] == ".":
            self.io.print_char("01"[_top(stack)])
        self.state = _advance(self.state, self.code, self.jumps)


def run(code: str, io: IO) -> None:
    """Run a BF-PDA program, halting when it reaches the end of the code."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
