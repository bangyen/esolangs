r"""Interpreter for bit~."""

from __future__ import annotations

import sys

from esolangs.interpreters.brackets import unmatched
from esolangs.interpreters.io import IO

# : One instant of a run:.
# : pointer, and the bit pool.
# : returns a new one rather.
# : ``tuple`` for the same.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : stores.
# :.
# : The field order starts.
# : still returns ``(tape,.
# : Reordering there would.
type _State = tuple[int, int, tuple[int, ...]]


def _grown(tape: tuple[int, ...], need: int) -> tuple[int, ...]:
    r"""Return ``tape`` extended with zeros to at least ``need`` cells."""
    return tape if need <= len(tape) else (*tape, *([0] * (need - len(tape))))


def _match(code: str, ind: int, step: int) -> int:
    r"""Return the index of the bracket matching ``code[ind]``."""
    start = ind
    depth = step
    while depth:
        ind += step
        if not 0 <= ind < len(code):
            # The scan walks away from the.
            # is the one it started from --.
            # not wherever the walk fell.
            raise unmatched(code[start], start)
        if code[ind] == "{":
            depth += 1
        elif code[ind] == "}":
            depth -= 1
    return ind


def _advance(
    state: _State,
    code: str,
    byte: int | None = None,
    target: int | None = None,
) -> _State:
    r"""Return the state after executing the character at the cursor."""
    ind, cell, tape = state
    char = code[ind]
    if char == "~":
        tape = (*tape[:cell], tape[cell] ^ 1, *tape[cell + 1 :])
    elif char == ">":
        # The window is eight cells.
        if cell + 8 > len(tape):
            tape = (*tape, 0)
        cell += 1
    elif char == "<":
        # ``<`` at the first cell is a.
        if cell:
            cell -= 1
    elif char == ")":
        bits = tuple(int(b) for b in f"{byte if byte is not None else 0:08b}")
        tape = _grown(tape, cell + 8)
        tape = (*tape[:cell], *bits, *tape[cell + 8 :])
    elif target is not None:
        # Both brackets, once the shell.
        ind = target
    return (ind + 1, cell, tape)


class _Machine:
    r"""Per-run bit~ state: the bit pool, the pointer, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Start with an eight-cell pool at the origin."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per.
        # and once by ``step``'s guard.
        self.size = len(code)
        self.state: _State = (0, 0, (0,) * 8)

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def cell(self) -> int:
        return self.state[1]

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.state[2])

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The pool is already a tuple,.
        # order this returned before.
        ind, cell, tape = self.state
        return (tape, cell, ind, self.io.position())

    def step(self) -> None:
        r"""Execute one character, advancing the cursor."""
        if self.halted:
            return
        ind, cell, tape = self.state
        char = self.code[ind]
        byte = target = None
        if char == ")":
            byte = self.io.input_char()
        elif char == "(":
            val = tape[cell : cell + 8]
            self.io.print_char(chr(int("".join(map(str, val)), 2)))
        elif char == "{" and not tape[cell]:
            target = _match(self.code, ind, 1)
        elif char == "}" and tape[cell]:
            target = _match(self.code, ind, -1)
        self.state = _advance(self.state, self.code, byte, target)


def run(code: str, io: IO) -> None:
    r"""Run a bit~ program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
