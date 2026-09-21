"""Interpreter for BrainIf.

Line-based: ``if <value> <command>`` runs when the cell equals the
value; commands increment, move, goto a line, read a byte, or output.
A line missing its operands raises :class:`ValueError`; exhausted input
raises :class:`EOFError`.  The guard reads the cell as it stands, so
``if 0 increment`` / ``if 1 increment`` both fire in one pass -- the
language's behaviour, and a reorder was reverted.  :func:`_advance` is
pure over an immutable ``_State``; :func:`_parse`, the I/O and the
malformed-line rejection are the shell's.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO
from esolangs.interpreters.persistent import (
    Chunked,
    append,
    chunked,
    flatten,
    get,
    length,
    put,
)

#: ``(ind, ptr, cells)``: an immutable value, rebound per step.  The
#: parsed line is a parameter, not a field.
type _State = tuple[int, int, Chunked[int]]

#: A line the transition can act on: ``(value, command, target)``.  ``None``
#: stands for a blank line, which advances the cursor and nothing else.
#: ``target`` is meaningful only for ``goto`` and is zero otherwise.
type _Line = tuple[int, str, int] | None


def _parse(line: str) -> _Line:
    """Return the parsed form of one source line, or raise if malformed.

    Commands are recognised by substring (the examples write ``increment``
    where the wiki says ``inc``).
    """
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
    # A guarded line naming no command is inert but well-formed: it tests
    # the cell, does nothing, and falls through like any other line.
    return (value, "", 0)


def _advance(state: _State, line: _Line, byte: int | None = None) -> _State:
    """Return the state after executing one parsed line.

    Pure; ``input``'s byte arrives as ``byte``.  The guard reads the cell
    *now*.  ``goto`` sets the cursor to target minus two so the shared
    increment lands on target minus one (lines number from one).
    """
    ind, ptr, cells = state
    if line is None:
        return (ind + 1, ptr, cells)
    value, command, target = line
    current = get(cells, ptr)
    if current == value:
        if command in ("increment", "inc"):
            # The tape is chunked (:mod:`esolangs.interpreters.persistent`),
            # so a write rebuilds one chunk rather than the whole tape.
            cells = put(cells, ptr, current + 1)
        elif command == "right":
            ptr += 1
            # A move past the right end grows the tape by one zero cell.
            if ptr == length(cells):
                cells = append(cells, 0)
        elif command == "left":
            # ``left`` at the origin is clamped rather than an error.
            ptr = max(0, ptr - 1)
        elif command == "goto":
            ind = target - 2
        elif command == "input":
            cells = put(cells, ptr, byte or 0)
    return (ind + 1, ptr, cells)


class _Machine:
    """A BrainIf run: one immutable ``_State``, rebound per step.

    A ``goto`` loop whose cell never leaves the tested value is a provable cycle.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Start with a single zero cell at the origin."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per line -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, 0, chunked((0,)))

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def cells(self) -> tuple[int, ...]:
        # The state's tape, flattened out of its chunks.  Brainfuck's
        # ``tape`` reads the same way, so the two tape languages agree.
        return flatten(self.state[2])

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    # ``_TapeMachine`` view (no write buffer here).  BrainIf qualifies:
    # ``right`` appends one zero, ``left`` clamps at 0, everything else
    # touches only ``cells[ptr]``.

    @property
    def tape(self) -> tuple[int, ...]:
        """The cells, under the name the growth detector reads."""
        return flatten(self.state[2])

    def input_position(self) -> int:
        """Report the input cursor for the growth detector."""
        return self.io.position()

    @property
    def halted(self) -> bool:
        """Whether the cursor has passed the last line."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Cell tape + line cursor; ip the cursor, memory the
    # cells.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(flatten(self.state[2]))

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The cells are already a tuple, so they go in as they stand.  The
        # input cursor joins them because a repeat that ignores consumed
        # input is not a real cycle.
        ind, ptr, cells = self.state
        return (cells, ind, ptr, self.io.position())

    def step(self) -> None:
        """Execute one line, advancing the cursor.

        The shell parses, does I/O and rejects; I/O happens only when the guard
        passes, so an ``input`` whose guard fails consumes nothing.
        """
        if self.halted:
            return
        parsed = _parse(self.code[self.state[0]])
        byte = None
        if parsed is not None:
            _ind, ptr, cells = self.state
            value, command, _target = parsed
            if get(cells, ptr) == value:
                if command == "output":
                    self.io.print_char(chr(value))
                elif command == "input":
                    # The original skips empty reads rather than storing
                    # one, so a blank input line is not a zero byte.
                    while not (s := self.io.input_str()):
                        pass
                    byte = ord(s[0])
        self.state = _advance(self.state, parsed, byte)


def run(code: list[str], io: IO) -> None:
    """Run a BrainIf program."""
    parsed: dict[int, _Line] = {}
    cells = [0]
    ptr = 0
    ind = 0
    size = len(code)
    while ind < size:
        if ind not in parsed:
            parsed[ind] = _parse(code[ind])
        line = parsed[ind]
        if line is None:
            ind += 1
            continue

        value, command, target = line
        if cells[ptr] != value:
            ind += 1
            continue
        if command in ("increment", "inc"):
            cells[ptr] += 1
        elif command == "right":
            ptr += 1
            if ptr == len(cells):
                cells.append(0)
        elif command == "left":
            ptr = max(0, ptr - 1)
        elif command == "goto":
            ind = target - 1
            continue
        elif command == "input":
            while not (text := io.input_str()):
                pass
            cells[ptr] = ord(text[0])
        elif command == "output":
            io.print_char(chr(value))
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
