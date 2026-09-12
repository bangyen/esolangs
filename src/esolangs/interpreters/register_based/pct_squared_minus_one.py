r"""Interpreter for %^2^-1."""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : accumulator.
# : one rather than editing one.
# :.
# : This is exactly what.
# : state and its hashable view.
# : whose tape needs committing.
# : second spelling of a.
# :.
# : A plain tuple rather than a.
# : unpacking in the functions.
# : ``NamedTuple.__new__`` is.
#: C-level.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : stores.
type _State = tuple[int, int]


def _reset(state: _State) -> _State:
    r"""Return ``state`` with an over-3003 accumulator zeroed."""
    ind, acc = state
    return (ind, 0) if acc > 3003 else state


def _advance(state: _State, code: str) -> _State:
    r"""Return the state after executing the command at the code position."""
    ind, acc = _reset(state)
    char = code[ind]
    if char == "s":
        acc -= 2
    elif char == "i":
        acc -= 3
    elif char == "m":
        acc *= 2
    elif char == "p":
        acc *= -1
    elif char == "'":
        acc = 0
    elif char == "t" and acc != 0:
        # The rewind lands on position.
        # so it returns directly rather.
        return (0, acc)
    return (ind + 1, acc)


class _Machine:
    r"""A %^2^-1 run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Store ``code`` and start the accumulator at zero."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        # rather than recomputed on.
        self.size = len(code)
        self.state: _State = (0, 0)

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def acc(self) -> int:
        return self.state[1]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the program."""
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # accumulator.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.state[1]]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The state as it stands: it is.
        # returned before the split,.
        return self.state

    def step(self) -> None:
        r"""Execute one command, resetting the accumulator first if too large."""
        if self.state[0] >= self.size:
            return
        state = _reset(self.state)
        ind, acc = state
        char = self.code[ind]
        if char == "l":
            self.io.print_num(acc)
        elif char == "e":
            self.io.print_char(chr(acc & 0xFF))
        elif char == "n":
            state = (ind, self.io.input_char())
        self.state = _advance(state, self.code)


def run(code: str, io: IO) -> None:
    r"""Run a %^2^-1 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
