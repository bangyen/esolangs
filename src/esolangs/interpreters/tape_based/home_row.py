r"""Interpreter for Home Row."""

from __future__ import annotations

import sys

from esolangs.interpreters.brackets import unmatched
from esolangs.interpreters.io import IO

# : One instant of a run:.
# : pointer, and the 25 cells.
# : returns a new one rather.
# : ``tuple`` for the same.
# :.
# : This is exactly what.
# : state and its hashable view.
# :.
# : The code and its loop.
# : changes during a run, so.
# : value the cycle detector.
type _State = tuple[int, int, tuple[int, ...]]


def _matches(code: str) -> tuple[dict[int, int], set[int]]:
    r"""Return ``{l: partner}`` and the set of loop-open indices."""
    stack: list[int] = []
    match: dict[int, int] = {}
    open_l: set[int] = set()
    for i, char in enumerate(code):
        if char != "l":
            continue
        if not stack:
            stack.append(i)
            open_l.add(i)
        else:
            j = stack.pop()
            match[i] = j
            match[j] = i
    if stack:
        # One glyph both opens and.
        # from `match_brackets`; the.
        raise unmatched("l", stack[-1])
    return match, open_l


def _advance(
    state: _State,
    code: str,
    match: dict[int, int],
    open_l: set[int],
) -> _State:
    r"""Return the state after executing the command at the cursor."""
    ind, ptr, grid = state
    char = code[ind]
    if char == "a":
        grid = (*grid[:ptr], grid[ptr] + 1, *grid[ptr + 1 :])
    elif char == "s":
        # Cells are unbounded, so ``s``.
        grid = (*grid[:ptr], grid[ptr] - 1, *grid[ptr + 1 :])
    elif char == "d":
        ptr = (ptr + 5) % 25
    elif char == "f":
        ptr += 1
        if ptr % 5 == 0:
            ptr -= 5
    elif char == "j":
        # Skip the next command when.
        if grid[ptr] == 0:
            ind += 1
    elif char == "k":
        # The print already happened in.
        grid = (*grid[:ptr], 0, *grid[ptr + 1 :])
    elif char == "l":
        partner = match[ind]
        if ind in open_l:
            if grid[ptr] == 0:
                ind = partner
        elif grid[ptr] != 0:
            ind = partner
    return (ind + 1, ptr, grid)


class _Machine:
    r"""Per-run Home Row state: the grid, pointer, and code cursor."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Match ``code``'s loop pairs and start the grid at all zeros."""
        self.io = io
        self.code = code
        self.match, self.open_l = _matches(code)
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(code)
        self.state: _State = (0, 0, (0,) * 25)

    # The language's own names.
    # than fields of their own, so.

    @property
    def grid(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has run off the program or hit ``;``."""
        ind = self.state[0]
        return ind >= self.size or self.code[ind] == ";"

    # The VM's language-shaped.
    # the 25 cells.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.state[0]

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
        # The state as it stands: it is.
        # this returned before the.
        return self.state

    def step(self) -> None:
        r"""Execute one command, advancing the cursor."""
        if self.halted:
            return
        ind, ptr, grid = self.state
        if self.code[ind] == "k":
            self.io.print_char(chr(grid[ptr] & 0xFF))
        self.state = _advance(self.state, self.code, self.match, self.open_l)


def run(code: str, io: IO) -> None:
    r"""Run a Home Row program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
