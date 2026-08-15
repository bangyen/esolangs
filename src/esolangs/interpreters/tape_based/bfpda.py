"""Interpreter for BF-PDA.

A brainfuck variant over a stack of bits whose top is the current cell.
``@`` flips the top bit, ``.`` prints the top bit as ``'0'``/``'1'``, ``<``
pushes a zero, ``>`` pops the top bit, and ``[``/``]`` are brainfuck-style
while loops (``[`` skips to its matching ``]`` when the top bit is 0, ``]``
jumps back when it is 1).  All other characters are comments.

Per the wiki, an empty stack behaves as a zero: ``>`` pops nothing, and any
peek (``@``, ``.``, ``[``) reads 0 (``@`` pushes that zero and flips it to
1).  A run is bounded at ``limit`` commands so `#eval`-style loops that never
empty the stack terminate.
"""

import sys

from esolangs.exceptions import HaltError
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
            if stack:
                stack[-1] ^= 1
            else:
                stack.append(1)  # auto-push the zero, then flip it
            ip += 1
        elif c == ".":
            io.print_char("01"[stack[-1] if stack else 0])
            ip += 1
        elif c == "<":
            stack.append(0)
            ip += 1
        elif c == ">":
            if stack:
                stack.pop()
            ip += 1
        elif c == "[":
            if not stack or stack[-1] == 0:
                ip = _forward(code, ip)
            else:
                ip += 1
        elif c == "]":
            if stack and stack[-1] == 1:
                ip = _backward(code, ip)
            else:
                ip += 1
        else:
            ip += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
