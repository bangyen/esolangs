r"""Interpreter for BrainIf."""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : pointer, and the cells.
# : returns a new one rather.
# : ``tuple`` for the same.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : stores.
# :.
# : A plain tuple rather than a.
# : unpacking in the functions.
# : ``NamedTuple.__new__`` is.
#: C-level.
type _State = tuple[int, int, tuple[int, ...]]

# : A line the transition can.
# : stands for a blank line,.
# : ``target`` is meaningful.
type _Line = tuple[int, str, int] | None


def _parse(line: str) -> _Line:
    r"""Return the parsed form of one source line, or raise if malformed."""
    line = line.strip()
    if not line:
        return None
    arr = line.split()
    if len(arr) < 2:
        raise ValueError("malformed BrainIf line: " + line)
    value = int(arr[1])
    for name in ("increment", "inc", "right", "left", "goto", "input", "output"):
        if name in line:
            if name == "goto":
                if len(arr) < 4:
                    raise ValueError("goto requires a target line")
                return (value, "goto", int(arr[3]))
            return (value, name, 0)
    # A guarded line naming no.
    # the cell, does nothing, and.
    return (value, "", 0)


def _advance(state: _State, line: _Line, byte: int | None = None) -> _State:
    r"""Return the state after executing one parsed line."""
    ind, ptr, cells = state
    if line is None:
        return (ind + 1, ptr, cells)
    value, command, target = line
    if cells[ptr] == value:
        if command in ("increment", "inc"):
            cells = (*cells[:ptr], cells[ptr] + 1, *cells[ptr + 1 :])
        elif command == "right":
            ptr += 1
            # A move past the right end.
            if ptr == len(cells):
                cells = (*cells, 0)
        elif command == "left":
            # ``left`` at the origin is.
            ptr = max(0, ptr - 1)
        elif command == "goto":
            ind = target - 2
        elif command == "input":
            cells = (*cells[:ptr], byte or 0, *cells[ptr + 1 :])
    return (ind + 1, ptr, cells)


class _Machine:
    r"""A BrainIf run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: list[str], io: IO) -> None:
        r"""Start with a single zero cell at the origin."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(code)
        self.state: _State = (0, 0, (0,))

    # The language's own names.
    # than fields of their own, so.

    @property
    def cells(self) -> tuple[int, ...]:
        # The state's own tuple, handed.
        # ``tape`` reads the same way,.
        return self.state[2]

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    # The growth detector's view.
    # -- there is no write buffer.
    # tuple under the name.
    # ``ip`` (below) is the line.
    # protocol: ``right`` appends.
    # at cell 0 (``ptr = max(0, ptr.
    # or writes only ``cells[ptr]``.
    # cell under the pointer and.

    @property
    def tape(self) -> tuple[int, ...]:
        r"""The cells, under the name the growth detector reads."""
        return self.state[2]

    def input_position(self) -> int:
        r"""Report the input cursor for the growth detector."""
        return self.io.position()

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has passed the last line."""
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # cells.

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
        # The cells are already a.
        # input cursor joins them.
        # input is not a real cycle.
        ind, ptr, cells = self.state
        return (cells, ind, ptr, self.io.position())

    def step(self) -> None:
        r"""Execute one line, advancing the cursor."""
        if self.halted:
            return
        parsed = _parse(self.code[self.state[0]])
        byte = None
        if parsed is not None:
            _ind, ptr, cells = self.state
            value, command, _target = parsed
            if cells[ptr] == value:
                if command == "output":
                    self.io.print_char(chr(cells[ptr]))
                elif command == "input":
                    # The original skips empty.
                    # one, so a blank input line is.
                    while not (s := self.io.input_str()):
                        pass
                    byte = ord(s[0])
        self.state = _advance(self.state, parsed, byte)


def run(code: list[str], io: IO) -> None:
    r"""Run a BrainIf program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
