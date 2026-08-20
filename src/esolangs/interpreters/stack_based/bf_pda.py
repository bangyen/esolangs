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
"""

import sys

from esolangs.interpreters.io import IO


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
        self.stack: list[int] = []
        self.ip = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ip >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ip, tuple(self.stack))

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor."""
        if self.halted:
            return
        c = self.code[self.ip]
        if c == "@":
            if self.stack:
                self.stack[-1] ^= 1
            else:
                self.stack.append(1)  # auto-push the zero, then flip it
            self.ip += 1
        elif c == ".":
            self.io.print_char("01"[self.stack[-1] if self.stack else 0])
            self.ip += 1
        elif c == "<":
            self.stack.append(0)
            self.ip += 1
        elif c == ">":
            if self.stack:
                self.stack.pop()
            self.ip += 1
        elif c == "[":
            if not self.stack or self.stack[-1] == 0:
                self.ip = _forward(self.code, self.ip)
            else:
                self.ip += 1
        elif c == "]":
            if self.stack and self.stack[-1] == 1:
                self.ip = _backward(self.code, self.ip)
            else:
                self.ip += 1
        else:
            self.ip += 1


def run(code: str, io: IO) -> None:
    """Run a BF-PDA program, halting when it reaches the end of the code."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
