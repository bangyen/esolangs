r"""Interpreter for Circlefuck."""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters.brackets import unmatched
from esolangs.interpreters.io import IO

# : One instant of a run:.
# : data pointer, the tape, and.
# :.
# : ``done`` is state because.
# : pointer reaching an ``@``.
# : the tape is circular, so.
# :.
# : ``done`` stays out of.
# : plus the input cursor, in.
type _State = tuple[int, int, tuple[int, ...], bool]

# : The one change a cell makes.
# : cell, ``("insert", i, 0)``.
# : removes that cell, and.
# : applied so that recording a.
#: :func:`_advance`.
type _Edit = tuple[str, int, int] | None

# : What executing one cell.
# : already wrapped against the.
# : apply the edit and store.
type _Move = tuple[int, int, bool, _Edit]


def parse(code: str) -> list[int]:
    r"""Decode Circlefuck's escape sequences and keep printable commands."""
    reg = r"\\(?:\d\d\d|" r"[\dA-F](?:$|[^\d]))"
    exp = r"((^|[^\\]) |\\( )|(\\)o)"

    for s in re.findall(reg, code):
        if len(s) == 4:
            val = oct(int(s[1:]))
            new = val[2:].zfill(3)
        else:
            new = f"x0{s[1:]}"
        code = code.replace(s, f"\\{new}")

    code = re.sub(exp, r"\2\3\4", code)
    code = "".join(c for c in code if 31 < ord(c) < 127)
    code = bytes(code, "utf-8").decode("unicode_escape")

    return [ord(c) for c in code]


def find(code: Sequence[int], ind: int, ptr: int) -> int:
    r"""Return the matching bracket for ``ind``."""
    char = chr(code[ind])
    if char == "[":
        if code[ptr]:
            return ind
        mode = 1
    else:
        if not code[ptr]:
            return ind
        mode = -1

    match = mode
    start = ind
    num = len(code)

    while match:
        ind = (ind + mode) % num
        sym = chr(code[ind])
        if ind == start:
            # The walk wraps the ring and.
            # no partner is the one it set.
            raise unmatched(char, start)
        if sym == "[":
            match += 1
        elif sym == "]":
            match -= 1
    return ind


def _advance(
    cells: Sequence[int], ind: int, ptr: int, byte: int | None = None
) -> _Move:
    r"""Return what executing one cell does, without doing it."""
    char = chr(cells[ind])
    size = len(cells)
    edit: _Edit = None
    if char == ">":
        ptr = (ptr + 1) % size
    elif char == "<":
        ptr = (ptr - 1) % size
    elif char == "+":
        edit = ("set", ptr, (cells[ptr] + 1) % 256)
    elif char == "-":
        edit = ("set", ptr, (cells[ptr] - 1) % 256)
    elif char == ",":
        # Reduced like ``+`` and ``-``.
        # code point, so an input line.
        # that code point into a cell.
        # 0..255 -- and left it.
        # ``+`` reduced what ``,`` had.
        edit = ("set", ptr, (byte if byte is not None else 0) % 256)
    elif char in "[]":
        ind = find(cells, ind, ptr)
    elif char == "@":
        # The run stops on the ``@``.
        return (ind, ptr, True, None)
    elif char == "#":
        ind += 1
    elif char == "{":
        edit = ("insert", ptr, 0)
        size += 1
        ind += 1
    elif char == "}":
        edit = ("delete", ptr, 0)
        size -= 1
        ptr %= size
    return ((ind + 1) % size, ptr, False, edit)


class _Machine:
    r"""Per-run Circlefuck state: the tape (which is the program), and."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Parse ``code``; an empty program is malformed."""
        self.io = io
        cells = parse(code)
        if not cells:
            raise ValueError("Circlefuck program cannot be empty")
        # The shell owns the tape as a.
        # assignment rather than a.
        # copies it, so nothing outside.
        self._cells = cells
        self._ind = 0
        self._ptr = 0
        self._done = False

    # The language's own names.
    # out the list the shell.
    # under it and one logical.

    @property
    def state(self) -> _State:
        r"""The machine's fields as the value the old transition took."""
        return (self._ind, self._ptr, tuple(self._cells), self._done)

    @property
    def cells(self) -> tuple[int, ...]:
        r"""The tape, which is also the program."""
        return tuple(self._cells)

    @property
    def ind(self) -> int:
        return self._ind

    @property
    def ptr(self) -> int:
        return self._ptr

    @property
    def halted(self) -> bool:
        r"""Whether the pointer hit ``@``."""
        return self._done

    # The VM's language-shaped.
    # memory cells.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self._ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self._cells)

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # A tuple copy of the tape, not.
        # snapshots across steps, and a.
        # it and make a real repeat.
        # is the one this returned.
        return (tuple(self._cells), self._ind, self._ptr, self.io.position())

    def step(self) -> None:
        r"""Execute one cell, advancing the pointers."""
        if self._done:
            return
        cells = self._cells
        char = chr(cells[self._ind])
        byte = None
        if char == "}" and len(cells) == 1:
            # Deleting the last cell would.
            raise HaltError(
                "'}' deletes the current cell and this is the last one, "
                "so there would be no program left to run"
            )
        if char == ",":
            byte = self.io.input_char()
        elif char == ".":
            self.io.print_char(chr(cells[self._ptr]))
        self._ind, self._ptr, self._done, edit = _advance(
            cells, self._ind, self._ptr, byte
        )
        if edit is not None:
            kind, at, value = edit
            if kind == "set":
                cells[at] = value
            elif kind == "insert":
                cells.insert(at, value)
            else:
                del cells[at]


def run(code: str, io: IO) -> None:
    r"""Run a Circlefuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
