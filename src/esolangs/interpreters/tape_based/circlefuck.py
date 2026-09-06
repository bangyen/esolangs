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

The execution model splits the rules from the writing.  :func:`_advance` is
pure: it reads the tape and *reports* what one cell does -- the new cursors
and the single edit -- without touching anything.  It takes no ``io``
argument at all, so it is total and side-effect free by construction rather
than by inspection.

The tape is the program, so ``{`` and ``}`` move the code out from under the
cursor and the tape's length -- which every wrap is taken modulo -- is
something a step decides.  :func:`_advance` therefore wraps the cursors
against the length its own edit will produce, not the one it was handed.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It owns the tape as a list and applies each reported edit in place, so a
write costs one assignment.  Returning a rewritten tape instead meant
copying every cell to record one, which made a program that writes ``n``
times cost O(n**2); naming the edit made the same walk linear (22x at 96
characters of generated text).  Every observer -- ``cells``, ``memory``,
``state``, ``snapshot`` -- copies the list, so nothing outside the class can
reach it and one logical state keeps one spelling.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, ptr, cells, done)`` -- the code cursor, the
#: data pointer, the tape, and whether ``@`` has halted the run.
#:
#: ``done`` is state because halting here is a decision a cell makes -- the
#: pointer reaching an ``@`` -- rather than a position the cursor passes:
#: the tape is circular, so there is no end to run off.
#:
#: ``done`` stays out of ``snapshot``, which reports the three live fields
#: plus the input cursor, in the order it always returned them.
type _State = tuple[int, int, tuple[int, ...], bool]

#: The one change a cell makes to the tape: ``("set", i, value)`` writes a
#: cell, ``("insert", i, 0)`` grows the tape at ``i``, ``("delete", i, 0)``
#: removes that cell, and ``None`` leaves the tape alone.  Named rather than
#: applied so that recording a write does not copy the tape -- see
#: :func:`_advance`.
type _Edit = tuple[str, int, int] | None

#: What executing one cell did: ``(ind, ptr, done, edit)``.  The cursors are
#: already wrapped against the length the edit produces, so the shell can
#: apply the edit and store the cursors without recomputing anything.
type _Move = tuple[int, int, bool, _Edit]


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


def find(code: Sequence[int], ind: int, ptr: int) -> int:
    """Return the matching bracket for ``ind``.

    Raises :class:`ValueError` if the brackets are unbalanced: the wiki
    defines ``[``/``]`` only for matched pairs, so an unmatched bracket is a
    malformed program.

    Takes any read-only sequence, so the caller passes the tape it already
    holds rather than copying it into a list on every bracket.
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


def _advance(
    cells: Sequence[int], ind: int, ptr: int, byte: int | None = None
) -> _Move:
    """Return what executing one cell does, without doing it.

    Pure: it reads the tape and reports the change as a :data:`_Move` --
    the new cursors, whether the run stopped, and the one edit the cell
    makes.  It takes no ``io`` argument, so ``,`` and ``.`` are the
    caller's business -- ``.`` changes no state at all, and ``,``'s byte
    arrives already read.

    The edit is *named*, not applied, because the tape is also the program:
    rewriting it to record one changed cell copied the whole thing, so a
    program that writes ``n`` times cost O(n**2).  Naming the cell makes a
    write O(1) and leaves :meth:`_Machine.step` to apply it to the list it
    owns.  Self-modification still works exactly: the edit is applied
    before the next fetch, so a write onto the cursor's own cell is read
    back as the next instruction, and a write that lands ahead of the
    cursor is seen when the cursor arrives.

    ``{`` and ``}`` change the tape's *length*, and the wrap at the end is
    taken modulo the new one -- so they report the length their edit will
    produce rather than the one they were handed.  An insert at or before
    the cursor shifts the code under it, which is the language working as
    intended.

    ``#`` and ``{`` advance the cursor an extra cell, so they skip past
    what follows them; every other cell takes only the shared wrap.
    """
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
        edit = ("set", ptr, byte if byte is not None else 0)
    elif char in "[]":
        ind = find(cells, ind, ptr)
    elif char == "@":
        # The run stops on the ``@`` itself, without wrapping past it.
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
        # The shell owns the tape as a mutable list: a write is one
        # assignment rather than a rebuilt tuple.  Every observer below
        # copies it, so nothing outside this class can reach the list.
        self._cells = cells
        self._ind = 0
        self._ptr = 0
        self._done = False

    # The language's own names.  Each copies the tape rather than handing
    # out the list the shell mutates, so an observer's view never changes
    # under it and one logical state keeps one spelling.

    @property
    def state(self) -> _State:
        """The machine's fields as the value the old transition took."""
        return (self._ind, self._ptr, tuple(self._cells), self._done)

    @property
    def cells(self) -> tuple[int, ...]:
        """The tape, which is also the program."""
        return tuple(self._cells)

    @property
    def ind(self) -> int:
        return self._ind

    @property
    def ptr(self) -> int:
        return self._ptr

    @property
    def halted(self) -> bool:
        """Whether the pointer hit ``@``."""
        return self._done

    # The VM's language-shaped view: Self-modifying circular tape + cursor; ip cursor,
    # memory cells.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self._ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self._cells)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # A tuple copy of the tape, not the list itself: the detector holds
        # snapshots across steps, and a live reference would mutate under
        # it and make a real repeat compare unequal to itself.  The order
        # is the one this returned before ``done`` joined the state.
        return (tuple(self._cells), self._ind, self._ptr, self.io.position())

    def step(self) -> None:
        """Execute one cell, advancing the pointers.

        The two I/O cells and the last-cell rejection live here rather than
        in the transition: this is the shell, so it is where an effect or a
        raise belongs, and it leaves :func:`_advance` total.
        """
        if self._done:
            return
        cells = self._cells
        char = chr(cells[self._ind])
        byte = None
        if char == "}" and len(cells) == 1:
            # Deleting the last cell would leave nothing to run.
            raise HaltError
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
    """Run a Circlefuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
