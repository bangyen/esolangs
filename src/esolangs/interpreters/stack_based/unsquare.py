r"""Interpreter for Unsquare."""

from __future__ import annotations

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# : The largest value ``o`` can.
# : it must not hand to ``chr``.
_MAX_CHAR = 0x10FFFF
_SURROGATES = range(0xD800, 0xE000)

# : How many stack elements.
# : one that needs two; the.
#: this mapping needs none.
_NEEDS = {"A": 1, "o": 1, "S": 2}

# : One instant of a run:.
# : the accumulator, the data.
# : a record: every transition.
# : one in place, and both.
# :.
# : The jump stack is state,.
# : position a matching ``>``.
# : with different jump stacks.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : stores.
type _State = tuple[int, int, tuple[int, ...], tuple[int, ...]]


def _needs(char: str) -> int:
    r"""Return how many stack elements ``char`` requires to run."""
    return _NEEDS.get(char, 0)


def _forward(code: str, ind: int) -> int | None:
    r"""Return the position of the ``<`` matching the ``>`` at ``ind``."""
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
    r"""Return the state after executing the command at the cursor."""
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
        # The accumulator decides: 0 or.
        # enters it and records where.
        if acc in (0, 1):
            ind = target if target is not None else ind
        else:
            jumps = (*jumps, ind - 1)
    elif char == "<":
        ind, jumps = jumps[-1], jumps[:-1]
    return (ind + 1, acc, stack, jumps)


class _Machine:
    r"""Per-run Unsquare state: the stack, jump stack, accumulator, cursor."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Start with empty stacks, a zero accumulator, at the first token."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(code)
        self.state: _State = (0, 0, (), ())

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def acc(self) -> int:
        return self.state[1]

    @property
    def stack(self) -> tuple[int, ...]:
        r"""The data stack, bottom first."""
        return self.state[2]

    @property
    def jumps(self) -> tuple[int, ...]:
        return self.state[3]

    def load(self, stack: tuple[int, ...]) -> None:
        r"""Put ``stack`` under the machine without running anything."""
        ind, acc, _stack, jumps = self.state
        self.state = (ind, acc, tuple(stack), jumps)

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the program."""
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # above already is the view.

    @property
    def ip(self) -> int:
        r"""The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""The accumulator, the only cell this language addresses."""
        return [self.state[1]]

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # Both stacks are already.
        # the order this returned.
        ind, acc, stack, jumps = self.state
        return (ind, acc, stack, jumps, self.io.position())

    def step(self) -> None:
        r"""Execute one command, advancing the cursor."""
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
                self.state = (self.size, acc, stack, jumps)
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
    r"""Run an Unsquare program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
