"""Interpreter for BF-PDA.

A brainfuck variant over a stack of bits whose top is the current cell.
``@`` flips the top bit, ``.`` prints the top bit as ``'0'``/``'1'``, ``<``
pushes a zero, ``>`` pops the top bit, and ``[``/``]`` are bracket control.
All other characters are comments.  There is no input command.

The bracket semantics port the Lean reference (``extra/lean/esolangs/
Esolangs/bfpda.lean``) exactly.  Its ``find`` matches a bracket by counting
``[`` as +1 and ``]`` as -1 while scanning from the adjacent character, and
both ``[`` and ``]`` resume at the position after the bracket (``[`` enters
its body and ``]`` leaves it), so a matched pair runs its body exactly once
rather than looping as in plain brainfuck.  The reference bounds every run
at 100 commands (``Bfpda.limit``) so ``#eval`` terminates; this interpreter
keeps that bound, overridable as ``limit``.

The reference only reaches an empty-stack access as a runtime panic that
still exits 0 (continuing with a zero top bit), and it misruns unmatched
brackets silently.  This interpreter instead raises
:class:`~esolangs.exceptions.HaltError` for any top-bit access or pop on an
empty stack, and for unmatched brackets, and rejects an empty program as
malformed with :class:`ValueError`.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def _top(stack: list[int]) -> int:
    """Return the top bit, halting on an empty stack."""
    if not stack:
        raise HaltError("cannot read the top bit of an empty stack")
    return stack[-1]


def _forward(code: str, i: int) -> int:
    """Run the reference's forward ``find`` from a ``[`` at position ``i``.

    The reference scans from the next character counting ``[`` as +1 and
    ``]`` as -1, returning the position after the bracket once a match is
    confirmed.  ``run`` rejects unmatched brackets up front, so a match
    always exists and the scan terminates.
    """
    length = len(code)
    z = 1
    j = i + 1
    c = code[j] if j < length else "\0"
    while z != 0:
        if c == "[":
            z += 1
        elif c == "]":
            z -= 1
        j += 1
        c = code[j] if j < length else "\0"
    return i + 1


def _backward(code: str, i: int) -> int:
    """Run the reference's backward ``find`` from a ``]`` at position ``i``.

    The reference scans backward from the previous character counting ``[``
    as +1 and ``]`` as -1, returning the position after the bracket once a
    match is confirmed.  ``run`` rejects unmatched brackets up front, so a
    match always exists and the scan terminates.
    """
    z = -1
    j = max(i - 1, 0)
    c = code[j]
    while z != 0:
        if c == "[":
            z += 1
        elif c == "]":
            z -= 1
        j = max(j - 1, 0)
        c = code[j]
    return i + 1


def run(code: str, io: IO, limit: int = 100) -> None:
    """Run a BF-PDA program, processing at most ``limit`` commands."""
    if not code:
        raise ValueError("BF-PDA program cannot be empty")
    depth = 0
    for pos, ch in enumerate(code):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth < 0:
                raise HaltError(f"unmatched ']' at position {pos}")
    if depth:
        raise HaltError(f"unmatched '[' at position {code.rfind('[')}")

    n = len(code)
    stack: list[int] = []
    ip = 0
    for _ in range(limit):
        c = code[ip] if ip < n else "\0"
        if c == "@":
            stack[-1] = _top(stack) ^ 1
            ip += 1
        elif c == ".":
            io.print_char("01"[_top(stack)])
            ip += 1
        elif c == "<":
            stack.append(0)
            ip += 1
        elif c == ">":
            if not stack:
                raise HaltError("cannot pop an empty stack")
            stack.pop()
            ip += 1
        elif c == "[":
            if _top(stack) == 0:
                ip = _forward(code, ip)
            else:
                ip += 1
        elif c == "]":
            if _top(stack) == 1:
                ip = _backward(code, ip)
            else:
                ip += 1
        else:
            ip += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
