"""Interpreter for Circlefuck.

The tape is the program: cells wrap, ``+``/``-`` adjust, ``,`` reads,
``.`` prints, ``[``/``]`` jump to matching brackets, ``@`` halts,
``{``/``}`` insert and remove cells.  An empty program or unmatched
brackets raise :class:`ValueError`; deleting the last cell halts with
:class:`~esolangs.exceptions.HaltError`; EOF is a no-op.

:func:`_advance` is pure and *reports* one cell's edit and cursors,
wrapping against the length its own edit produces.  :class:`_Machine`
applies the edit in place on a list: returning a rewritten tape made
``n`` writes O(n**2) (22x slower at 96 generated characters).  Every
observer copies the list.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from functools import lru_cache

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.brackets import unmatched
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
    """Decode Circlefuck escapes, rejecting a stray backslash."""
    cells: list[int] = []
    ind = 0
    while ind < len(code):
        char = code[ind]
        if char != "\\":
            if 32 < ord(char) < 127:
                cells.append(ord(char))
            ind += 1
            continue
        ind += 1
        if ind >= len(code):
            raise ValueError("invalid Circlefuck escape")
        tail = code[ind:]
        if tail.startswith("space"):
            cells.append(32)
            ind += 5
        elif code[ind] == " ":
            cells.append(32)
            ind += 1
        elif code[ind] in "nrtb":
            cells.append({"n": 10, "r": 13, "t": 9, "b": 8}[code[ind]])
            ind += 1
        elif code[ind] == "\\":
            cells.append(92)
            ind += 1
        elif code[ind] == "o":
            digits = code[ind + 1 : ind + 4]
            if len(digits) != 3 or any(d not in "01234567" for d in digits):
                raise ValueError("invalid Circlefuck escape")
            cells.append(int(digits, 8))
            ind += 4
        elif code[ind] == "x":
            digits = code[ind + 1 : ind + 3]
            if len(digits) != 2 or any(
                d not in "0123456789abcdefABCDEF" for d in digits
            ):
                raise ValueError("invalid Circlefuck escape")
            cells.append(int(digits, 16))
            ind += 3
        elif code[ind].isdigit():
            digits = code[ind : ind + 3]
            if len(digits) == 3 and digits.isdigit():
                if int(digits) > 255:
                    raise ValueError("invalid Circlefuck escape")
                cells.append(int(digits))
                ind += 3
            else:
                cells.append(int(code[ind], 16))
                ind += 1
        elif code[ind] in "ABCDEF":
            cells.append(int(code[ind], 16))
            ind += 1
        else:
            raise ValueError("invalid Circlefuck escape")
    return cells


@lru_cache(maxsize=16)
def _parsed(code: str) -> tuple[int, ...]:
    """Return the parsed tape in a reusable immutable form."""
    return tuple(parse(code))


def find(code: Sequence[int], ind: int, ptr: int) -> int:
    """Return the matching bracket for ``ind``.

    Raises :class:`ValueError` on unbalanced brackets.  Takes any read-only
    sequence, so callers pass the tape they hold.
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
            # The walk wraps the ring and comes back, so the bracket with
            # no partner is the one it set out from.
            raise unmatched(char, start)
        if sym == "[":
            match += 1
        elif sym == "]":
            match -= 1
    return ind


def _advance(
    cells: Sequence[int], ind: int, ptr: int, byte: int | None = None
) -> _Move:
    """Return what executing one cell does, without doing it.

    Reports a :data:`_Move`: new cursors, whether the run stopped, and the
    one edit.  The edit is applied before the next fetch, so a write onto
    the cursor's cell is read back as the next instruction.  ``{``/``}``
    report the length their edit produces; ``#`` and ``{`` advance an extra
    cell.
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
    elif char == "," and byte is not None:
        # Reduced like ``+`` and ``-`` above: ``input_char`` returns a whole
        # code point, so an input line starting above U+00FF otherwise put
        # that code point into a cell the two arithmetic arms keep in
        # 0..255 -- and left it disagreeing with itself, since the next
        # ``+`` reduced what ``,`` had not.
        edit = ("set", ptr, byte % 256)
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
        ind += ptr <= ind
    elif char == "}":
        edit = ("delete", ptr, 0)
        size -= 1
        ind -= ptr < ind
        ptr %= size
    return ((ind + 1) % size, ptr, False, edit)


class _Machine:
    """Per-run Circlefuck state: the tape (which is the program), and pointers.

    ``halted`` is true once the pointer hits ``@``; tape plus pointers
    determine the next step, so a hang is a finite-state cycle.
    """

    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code``; an empty program is malformed."""
        self.io = io
        cells = list(_parsed(code))
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
        """Execute one cell, advancing the pointers."""
        if self._done:
            return
        cells = self._cells
        char = chr(cells[self._ind])
        byte = None
        if char == "}" and len(cells) == 1:
            # Deleting the last cell would leave nothing to run.
            raise HaltError(
                "'}' deletes the current cell and this is the last one, "
                "so there would be no program left to run"
            )
        if char == ",":
            with suppress(EOFError):
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
    script_main(run)
