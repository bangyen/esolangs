"""Interpreter for BF-PDA.

A brainfuck variant over a stack of bits whose top is the current cell.
``@`` flips the top bit, ``.`` prints the top bit as ``'0'``/``'1'``, ``<``
pushes a zero, ``>`` pops the top bit, and ``[``/``]`` are brainfuck-style
while loops (``[`` skips to its matching ``]`` when the top bit is 0, ``]``
jumps back when it is 1).  All other characters are comments.

Per the wiki, an empty stack behaves as a zero: ``>`` pops nothing, and any
peek (``@``, ``.``, ``[``) reads 0 (``@`` pushes that zero and flips it to
1).  A run ends when the instruction pointer reaches the end of the program,
so the machine halts naturally like brainfuck; programs whose loops never
empty the stack run forever.

There are no invalid runtime operations to halt on: an empty stack reads
as zero for every peek/pop, so every command is always well-defined once
the program itself is validated.  Malformed programs (empty, or unbalanced
brackets) raise :class:`ValueError`.

The interpreter runs on a :class:`_Machine` (the code, the bit stack, and
the instruction pointer), so it is step-capable: ``step()`` executes one
command and ``halted`` is true once the cursor reaches the end of the code.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the code to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  The
stack is a tuple, so a state is a value that can be stored, compared, and
hashed as it stands.

The transition is total without any help from a validity check, which is
unusual here: the wiki's empty-stack-reads-zero rule means every command is
defined on every state, and the only way a program can fail -- unbalanced
brackets, or an empty program -- is caught once in ``__init__`` before any
command runs.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what BF-PDA *does* stays in the
pure layer.  ``.``'s print is the language's only effect and is done by
``step`` before it calls the pure transition.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: One instant of a run: ``(ip, stack)`` -- the cursor and the bit stack.  A
#: value, not a record: every transition below returns a new one rather than
#: editing one in place, and the stack is a ``tuple`` for the same reason.
#:
#: This is exactly what ``snapshot`` returns, and always has been, so the
#: state and its hashable view are the same tuple.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[int, tuple[int, ...]]


def _top(stack: tuple[int, ...]) -> int:
    """Return the top bit, or zero for an empty stack.

    Per the wiki an empty stack behaves as a zero for every peek, so this
    is what makes the transition total: there is no state on which a peek
    is undefined.
    """
    return stack[-1] if stack else 0


def _forward(code: str, i: int) -> int:
    """Return the index after the ``]`` matching the ``[`` at ``i``."""
    depth = 1
    j = i + 1
    while depth:
        if code[j] == "[":
            depth += 1
        elif code[j] == "]":
            depth -= 1
        j += 1
    return j


def _backward(code: str, i: int) -> int:
    """Return the index after the ``[`` matching the ``]`` at ``i``."""
    depth = 1
    j = i - 1
    while depth:
        if code[j] == "]":
            depth += 1
        elif code[j] == "[":
            depth -= 1
        j -= 1
    return j + 1


def _advance(state: _State, code: str) -> _State:
    """Return the state after executing the command at the cursor.

    Pure, and total: the brackets were balanced in ``__init__`` so the two
    scans below always find their partner, and an empty stack reads as zero
    for every peek.  It takes no ``io`` argument, so ``.``'s print is the
    caller's business -- it changes no state at all.

    Every command sets the cursor itself rather than falling through to a
    shared increment, because the two brackets jump to a position *after*
    their partner rather than onto it.

    Anything that is not a command is a comment and simply advances.
    """
    ip, stack = state
    if code[ip] == "@":
        # An empty stack auto-pushes the zero the peek saw, then flips it.
        stack = (*stack[:-1], stack[-1] ^ 1) if stack else (1,)
    elif code[ip] == "<":
        stack = (*stack, 0)
    elif code[ip] == ">":
        # ``>`` on an empty stack pops nothing.
        stack = stack[:-1]
    elif code[ip] == "[":
        if _top(stack) == 0:
            return (_forward(code, ip), stack)
    elif code[ip] == "]" and _top(stack) == 1:
        return (_backward(code, ip), stack)
    return (ip + 1, stack)


class _Machine:
    """Per-run BF-PDA state: the code, the bit stack, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Validate ``code``'s brackets and start with an empty stack.

        ``code`` must be non-empty and its brackets balanced; both are
        malformed-program conditions raised eagerly, before any command
        runs.
        """
        if not code:
            raise ValueError("BF-PDA program cannot be empty")
        depth = 0
        for pos, ch in enumerate(code):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth < 0:
                    raise ValueError(f"unmatched ']' at position {pos}")
        if depth:
            raise ValueError(f"unmatched '[' at position {code.rfind('[')}")

        self.io = io
        self.code = code
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

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

    # The VM's language-shaped view: a stack of bits whose top is the
    # current cell, so the store *is* the stack and ``memory`` is empty.
    # ``ip`` and ``stack`` above already are the view.

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The state as it stands: it is already the (ip, stack) pair this
        # returned before the split, and it is already hashable.
        return self.state

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor.

        ``.``'s print is here rather than in the transition: this is the
        shell, so it is where an effect belongs.  It reads the top through
        :func:`_top`, so an empty stack prints ``'0'`` like any other peek.
        """
        if self.halted:
            return
        ip, stack = self.state
        if self.code[ip] == ".":
            self.io.print_char("01"[_top(stack)])
        self.state = _advance(self.state, self.code)


def run(code: str, io: IO) -> None:
    """Run a BF-PDA program, halting when it reaches the end of the code."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
