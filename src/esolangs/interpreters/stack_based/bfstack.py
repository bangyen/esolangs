r"""Interpreter for BFStack."""

from __future__ import annotations

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# : One instant of a run:.
# : stack, and the loop stack.
# : returns a new one rather.
#: tuples for the same reason.
# :.
# : The loop stack is state,.
# : position a matching ``[``.
# : command with different loop.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : stores.
type _State = tuple[int, tuple[int, ...], tuple[int, ...]]

# : The commands that read the.
# : an empty one.
# : operand; ``]`` needs a.
_NEEDS_OPERAND = frozenset("<+-.[")


def _needs_operand(char: str) -> bool:
    r"""Whether ``char`` requires a non-empty data stack to run."""
    return char in _NEEDS_OPERAND


def _forward(code: str, ind: int) -> int | None:
    r"""Return the position of the ``]`` matching the ``[`` at ``ind``."""
    match = 1
    while match:
        ind += 1
        if ind == len(code):
            return None
        if (char := code[ind]) == "[":
            match += 1
        elif char == "]":
            match -= 1
    return ind


def _advance(state: _State, code: str, byte: int | None = None) -> _State:
    r"""Return the state after executing the command at the cursor."""
    ind, stk, lst = state
    char = code[ind]
    if char == ">":
        stk = (*stk, 0)
    elif char == "<":
        stk = stk[:-1]
    elif char == "+":
        stk = (*stk[:-1], (stk[-1] + 1) % 256)
    elif char == "-":
        stk = (*stk[:-1], (stk[-1] - 1) % 256)
    elif char == ",":
        stk = (*stk, byte if byte is not None else 0)
    elif char == "[":
        if stk[-1]:
            lst = (*lst, ind)
        else:
            # Skipping the loop: the shell.
            # cannot fail here.
            # threaded through, which keeps.
            target = _forward(code, ind)
            ind = target if target is not None else ind
    elif char == "]":
        ind, lst = lst[-1] - 1, lst[:-1]
    return (ind + 1, stk, lst)


class _Machine:
    r"""A BFStack run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Start with an empty data stack and loop stack."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(code)
        self.state: _State = (0, (), ())

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def stk(self) -> tuple[int, ...]:
        return self.state[1]

    @property
    def lst(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped view.
    # ``stack`` carries it and.
    # control flow, not addressable.

    @property
    def ip(self) -> int:
        r"""The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""BFStack addresses no cells; its store is the stack."""
        return []

    @property
    def stack(self) -> list[int]:
        r"""The data stack, bottom first."""
        # A list, because that is the.
        # It is a fresh one every time.
        # into a running machine -- the.
        return list(self.state[1])

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # Both stacks are already.
        ind, stk, lst = self.state
        return (stk, lst, ind, self.io.position())

    def step(self) -> None:
        r"""Execute one command, advancing the cursor."""
        if self.halted:
            return
        ind, stk, lst = self.state
        char = self.code[ind]
        if _needs_operand(char) and not stk:
            raise HaltError(
                f"{char!r} at position {ind} needs a value on the stack and "
                f"the stack is empty"
            )
        if char == "]" and not lst:
            raise HaltError(f"']' at position {ind} closes a loop that never opened")
        if char == "[" and not stk[-1] and _forward(self.code, ind) is None:
            # The original scanned the.
            # the bracket was unmatched,.
            # caller that catches the error.
            # is moved here rather than.
            self.state = (self.size, stk, lst)
            raise ValueError("unmatched '['")
        byte = None
        if char == ".":
            self.io.print_char(chr(stk[-1]))
        elif char == ",":
            byte = self.io.input_char()
        self.state = _advance(self.state, self.code, byte)


def run(code: str, io: IO) -> None:
    r"""Run a BFStack program, halting on an invalid empty-stack operation."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
