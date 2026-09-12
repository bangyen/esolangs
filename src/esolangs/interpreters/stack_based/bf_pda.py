r"""Interpreter for BF-PDA."""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : value, not a record: every.
# : editing one in place, and.
# :.
# : This is exactly what.
# : state and its hashable view.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : stores.
type _State = tuple[int, tuple[int, ...]]


def _top(stack: tuple[int, ...]) -> int:
    r"""Return the top bit, or zero for an empty stack."""
    return stack[-1] if stack else 0


def _forward(code: str, i: int) -> int:
    r"""Return the index after the ``]`` matching the ``[`` at ``i``."""
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
    r"""Return the index after the ``[`` matching the ``]`` at ``i``."""
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
    r"""Return the state after executing the command at the cursor."""
    ip, stack = state
    if code[ip] == "@":
        # An empty stack auto-pushes.
        stack = (*stack[:-1], stack[-1] ^ 1) if stack else (1,)
    elif code[ip] == "<":
        stack = (*stack, 0)
    elif code[ip] == ">":
        # ``>`` on an empty stack pops.
        stack = stack[:-1]
    elif code[ip] == "[":
        if _top(stack) == 0:
            return (_forward(code, ip), stack)
    elif code[ip] == "]" and _top(stack) == 1:
        return (_backward(code, ip), stack)
    return (ip + 1, stack)


class _Machine:
    r"""Per-run BF-PDA state: the code, the bit stack, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Validate ``code``'s brackets and start with an empty stack."""
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
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(code)
        self.state: _State = (0, ())

    # The language's own names.
    # than fields of their own, so.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.state[0]

    @property
    def stack(self) -> tuple[int, ...]:
        r"""The bit stack, bottom first."""
        return self.state[1]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # current cell, so the store.
    # ``ip`` and ``stack`` above.

    @property
    def memory(self) -> list[int]:
        r"""No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The state as it stands: it is.
        # returned before the split,.
        return self.state

    def step(self) -> None:
        r"""Execute one command, advancing (or jumping) the cursor."""
        if self.halted:
            return
        ip, stack = self.state
        if self.code[ip] == ".":
            self.io.print_char("01"[_top(stack)])
        self.state = _advance(self.state, self.code)


def run(code: str, io: IO) -> None:
    r"""Run a BF-PDA program, halting when it reaches the end of the code."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
