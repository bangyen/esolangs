"""Interpreter for Circlefuck.

The tape is the program itself: cells wrap, + and - adjust the current cell,
, reads input, . outputs, [ and ] jump to matching brackets reading the cell,
@ halts, { and } insert and remove cells, and the pointer moves around the
circular tape.

A program with no instructions is malformed and is rejected with
:class:`ValueError`, as is one with unmatched ``[``/``]`` brackets; deleting
the last cell (``}``) is an invalid operation and halts the program with
:class:`~esolangs.exceptions.HaltError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state to the next state, and never mutates what it
is given.  It takes no ``io`` argument at all, so it is total and
side-effect free by construction rather than by inspection.

The cells have to be in the state rather than beside it, and not only
because they change: they *are* the program.  ``{`` and ``}`` insert and
remove cells, so the code the cursor is walking moves out from under it,
and the tape's length -- which every wrap is taken modulo -- is something a
step decides.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Circlefuck *does* stays in
the pure layer.
"""

from __future__ import annotations

import re
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, ptr, cells, done)`` -- the code cursor, the
#: data pointer, the tape, and whether ``@`` has halted the run.  A value,
#: not a record: every transition below returns a new one rather than
#: editing one in place, and the tape is a ``tuple`` for the same reason.
#:
#: ``done`` is state because halting here is a decision a cell makes -- the
#: pointer reaching an ``@`` -- rather than a position the cursor passes:
#: the tape is circular, so there is no end to run off.
#:
#: ``done`` stays out of ``snapshot``, which reports the three live fields
#: plus the input cursor, in the order it always returned them.
type _State = tuple[int, int, tuple[int, ...], bool]


def parse(code: str) -> list[int]:
    """Decode Circlefuck's escape sequences and keep printable commands only."""
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


def find(code: list[int], ind: int, ptr: int) -> int:
    """Return the matching bracket for ``ind``.

    Raises :class:`ValueError` if the brackets are unbalanced: the wiki
    defines ``[``/``]`` only for matched pairs, so an unmatched bracket is a
    malformed program.
    """
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
            raise ValueError("unmatched bracket")
        if sym == "[":
            match += 1
        elif sym == "]":
            match -= 1
    return ind


def _advance(state: _State, byte: int | None = None) -> _State:
    """Return the state after executing one cell.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so ``,`` and ``.`` are the caller's business -- ``.`` changes
    no state at all, and ``,``'s byte arrives already read.

    ``{`` and ``}`` change the tape's *length*, and the wrap at the end is
    taken modulo the new one.  An insert at or before the cursor shifts the
    code under it, which is the language working as intended: the tape is
    the program.

    ``#`` and ``{`` advance the cursor an extra cell, so they skip past
    what follows them; every other cell takes only the shared wrap.
    """
    ind, ptr, cells, _done = state
    char = chr(cells[ind])
    if char == ">":
        ptr = (ptr + 1) % len(cells)
    elif char == "<":
        ptr = (ptr - 1) % len(cells)
    elif char == "+":
        cells = (*cells[:ptr], (cells[ptr] + 1) % 256, *cells[ptr + 1 :])
    elif char == "-":
        cells = (*cells[:ptr], (cells[ptr] - 1) % 256, *cells[ptr + 1 :])
    elif char == ",":
        cells = (*cells[:ptr], byte if byte is not None else 0, *cells[ptr + 1 :])
    elif char in "[]":
        ind = find(list(cells), ind, ptr)
    elif char == "@":
        # The run stops on the ``@`` itself, without wrapping past it.
        return (ind, ptr, cells, True)
    elif char == "#":
        ind += 1
    elif char == "{":
        cells = (*cells[:ptr], 0, *cells[ptr:])
        ind += 1
    elif char == "}":
        cells = (*cells[:ptr], *cells[ptr + 1 :])
        ptr %= len(cells)
    return ((ind + 1) % len(cells), ptr, cells, False)


class _Machine:
    """Per-run Circlefuck state: the tape (which is the program), and pointers.

    ``step()`` executes one cell and wraps the instruction pointer around the
    circular tape; ``halted`` is true once the pointer hits ``@``.  The tape
    and both pointers fully determine the next step, so a program that never
    halts is a finite-state cycle the hang detector can prove.  The VM and
    the hang detector expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code``; an empty program is malformed."""
        self.io = io
        cells = parse(code)
        if not cells:
            raise ValueError("Circlefuck program cannot be empty")
        self.state: _State = (0, 0, tuple(cells), False)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def cells(self) -> tuple[int, ...]:
        """The tape, which is also the program."""
        return self.state[2]

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def halted(self) -> bool:
        """Whether the pointer hit ``@``."""
        return self.state[3]

    # The VM's language-shaped view: Self-modifying circular tape + cursor; ip cursor,
    # memory cells.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.state[2])

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The tape is already a tuple, so it goes in as it stands, in the
        # order this returned before ``done`` joined the state.
        ind, ptr, cells, _done = self.state
        return (cells, ind, ptr, self.io.position())

    def step(self) -> None:
        """Execute one cell, advancing the pointers.

        The two I/O cells and the last-cell rejection live here rather than
        in the transition: this is the shell, so it is where an effect or a
        raise belongs, and it leaves :func:`_advance` total.
        """
        ind, ptr, cells, done = self.state
        if done:
            return
        char = chr(cells[ind])
        byte = None
        if char == "}" and len(cells) == 1:
            # Deleting the last cell would leave nothing to run.
            raise HaltError
        if char == ",":
            byte = self.io.input_char()
        elif char == ".":
            self.io.print_char(chr(cells[ptr]))
        self.state = _advance(self.state, byte)


def run(code: str, io: IO) -> None:
    """Run a Circlefuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
