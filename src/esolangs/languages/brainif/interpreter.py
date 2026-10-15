"""Interpreter for BrainIf.

One command a line: ``if <value> <command>`` runs when the cell equals the
value; commands increment, move, goto a line, read a byte, or output.
Cells are wrapping bytes: the page gives BrainIf "an identical memory
tape" to brainfuck, whose bytes wrap here (so ``if 256 ...`` never fires).
A line missing its operands, or ``goto 0`` ("line numbers starting at
1"), raises :class:`ValueError` when reached, guard or not; exhausted input
raises :class:`EOFError`.  ``move left`` at the leftmost cell grows the
tape a zero cell on the left: the spec says nothing about the left edge,
and cells left of the start are allowed.  The guard reads the
cell as it stands, so ``if 0 increment`` / ``if 1 increment`` both fire in
one pass -- the language's behaviour, and a reorder was reverted.
"""

from __future__ import annotations

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import parse_integer
from esolangs.runtime.persistent import (
    Chunked,
    append,
    chunked,
    flatten,
    get,
    length,
    prepend,
    put,
)
from esolangs.runtime.source_hints import keyword_hint, syntax_error

#: ``(ind, ptr, cells)``: an immutable value, rebound per step.  The
#: parsed line is a parameter, not a field.
type _State = tuple[int, int, Chunked[int]]

#: A line the transition can act on: ``(value, command, target)``.  ``None``
#: stands for a blank line, which advances the cursor and nothing else.
#: ``target`` is meaningful only for ``goto`` and is zero otherwise.
type _Line = tuple[int, str, int] | None

_COMMANDS = ("increment", "inc", "right", "left", "move", "goto", "input", "output")


def _parse(line: str) -> _Line:
    """Return the parsed form of one source line, or raise if malformed.

    Commands are whole whitespace-delimited words; ``inc`` also names
    ``increment``. Unknown commands raise ValueError, even on a false guard.
    """
    line = line.strip()
    if not line:
        return None
    arr = line.split()
    if len(arr) < 2 or arr[0] != "if":
        raise syntax_error(
            "malformed BrainIf line: " + line,
            "write if <integer> <command>, for example if 0 increment",
        )
    value = parse_integer(arr[1])
    command = arr[2] if len(arr) > 2 else ""
    if command == "move":
        if len(arr) != 4 or arr[3] not in ("right", "left"):
            raise syntax_error(
                "malformed BrainIf line: " + line,
                "write if <integer> move left or move right",
            )
        return (value, arr[3], 0)
    if command == "goto":
        if len(arr) < 4:
            raise syntax_error(
                "goto requires a target line",
                "write if <integer> goto <positive line number>",
            )
        if len(arr) != 4:
            raise syntax_error(
                "malformed BrainIf line: " + line,
                "give goto exactly one target line, for example if 0 goto 1",
            )
        target = parse_integer(arr[3])
        if target < 1:
            raise syntax_error(
                "goto target must be a positive line number",
                "number target lines from 1",
            )
        return (value, command, target)
    if len(arr) > 3:
        raise syntax_error(
            "malformed BrainIf line: " + line,
            "give the guarded command only its required operands",
        )
    if command in _COMMANDS:
        return (value, command, 0)
    raise syntax_error(
        f"unknown BrainIf command {command!r}",
        keyword_hint(
            command,
            _COMMANDS,
            "write increment, move left/right, goto <line>, input or output",
        ),
    )


# :func:`_advance` is pure over an immutable ``_State``; :func:`_parse`, the I/O and
# the malformed-line rejection are the shell's.
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
            # The tape is chunked (:mod:`esolangs.runtime.persistent`),
            # so a write rebuilds one chunk rather than the whole tape.
            cells = put(cells, ptr, (current + 1) % 256)
        elif command == "right":
            ptr += 1
            # A move past the right end grows the tape by one zero cell.
            if ptr == length(cells):
                cells = append(cells, 0)
        elif command == "left":
            # At cell 0 the tape grows a zero cell on the left, and index 0
            # is now that cell.  The spec says nothing about the left edge,
            # and cells left of the start are allowed.
            if ptr:
                ptr -= 1
            else:
                cells = prepend(cells, 0)
        elif command == "goto":
            ind = target - 2
        elif command == "input":
            cells = put(cells, ptr, (byte or 0) % 256)
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
    # ``right`` appends one zero; ``left`` at 0 prepends one, so ``ptr``
    # counts from the leftmost cell and a period that grows left passes
    # ``ptr == 0``, which the certificate's ``m >= 1`` rejects; everything
    # else touches only ``cells[ptr]``.

    @property
    def tape(self) -> tuple[int, ...]:
        """The cells, under the name the growth detector reads."""
        return flatten(self.state[2])

    def input_position(self) -> int:
        """Report the input cursor for the growth detector."""
        return self.io.progress()

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

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The cells are already a tuple, so they go in as they stand.  The
        # input cursor joins them because a repeat that ignores consumed
        # input is not a real cycle.
        ind, ptr, cells = self.state
        return (cells, ind, ptr, self.io.progress())

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
                    byte = self.io.input_char()
        self.state = _advance(self.state, parsed, byte)


def run(code: list[str], io: IO) -> None:
    """Run a BrainIf program through its pure transition."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run, shape="keep")
