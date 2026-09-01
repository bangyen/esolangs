"""Interpreter for BrainIf.

Line-based: each ``if <value> <command>`` runs only when the cell equals
<value>.  Commands increment, move right/left, goto a line, read a byte of
input, or output the current cell.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and a parsed line to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  The
cells are a tuple, so a state is a value that can be stored, compared, and
hashed as it stands.

:class:`_Machine` is the mutable shell the interpreter protocol requires
(``esolangs.vm`` wraps it and the hang detector steps it).  It holds one
``_State`` and rebinds it each step, so the mutation lives in exactly one
assignment and every rule about what BrainIf *does* stays in the pure
layer.  Two things stay in the shell because a total transition cannot do
them: the ``input``/``output`` effects, and rejecting a malformed line.

Parsing is likewise the shell's job.  :func:`_parse` turns a line into the
``(value, command, target)`` a transition needs, or raises -- so
:func:`_advance` receives something already known to be well-formed and has
no error case of its own.  This is what keeps the transition total: every
line it can be handed has a defined successor state.

A command line missing its required operands (``if`` without a value, or
``goto`` without a target) is a malformed program and is rejected with
:class:`ValueError`.

The guard is tested against the cell as it stands when the line runs, which
means an adjacent pair like ``if 0 increment`` / ``if 1 increment`` both
fire on a single pass -- the second tests the value the first just wrote.
That is the language's behaviour, not an oversight, and a previous attempt
to reorder it was reverted; the transition below reproduces it exactly by
testing the guard against the current state rather than a saved one.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, ptr, cells)`` -- the line cursor, the tape
#: pointer, and the cells.  A value, not a record: every transition below
#: returns a new one rather than editing one in place, and the cells are a
#: ``tuple`` for the same reason.
#:
#: The code is deliberately *not* in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  The parsed line is a parameter to the transition instead.
#:
#: A plain tuple rather than a ``NamedTuple``: the fields are read by
#: unpacking in the functions that use them, so the names bought little, and
#: ``NamedTuple.__new__`` is Python-level where the tuple constructor is
#: C-level.
type _State = tuple[int, int, tuple[int, ...]]

#: A line the transition can act on: ``(value, command, target)``.  ``None``
#: stands for a blank line, which advances the cursor and nothing else.
#: ``target`` is meaningful only for ``goto`` and is zero otherwise.
type _Line = tuple[int, str, int] | None


def _parse(line: str) -> _Line:
    """Return the parsed form of one source line, or raise if malformed.

    This is where a program can be rejected, which is precisely why it is
    not in :func:`_advance`: the transition should have no error case, so
    everything that can fail happens before it is called.

    The command is recognised by substring, as the original did -- the
    language's own examples write ``increment`` where the wiki says
    ``inc`` -- so the whole line is searched rather than a fixed token.
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

    Pure: it reads ``state`` and returns a new one, and every command that
    is not I/O is decided entirely here.  It takes no ``io`` argument, so
    ``input`` and ``output`` are necessarily the caller's business; this
    function sees only what they leave behind -- ``output`` changes no state
    at all, and ``input``'s byte arrives as ``byte``, already read.

    The guard reads the cell under the pointer *now*, not a value saved
    before the line ran.  That is what produces the documented double-fire
    of an adjacent guard pair, and it is load-bearing.

    ``goto`` sets the cursor to its target minus two, because the shared
    increment below then lands it on target minus one -- the language
    numbers lines from one.  Every other command falls through to that same
    increment, which is what makes the cursor advance exactly once per call.
    """
    ind, ptr, cells = state
    if line is None:
        return (ind + 1, ptr, cells)
    value, command, target = line
    if cells[ptr] == value:
        if command in ("increment", "inc"):
            cells = (*cells[:ptr], cells[ptr] + 1, *cells[ptr + 1 :])
        elif command == "right":
            ptr += 1
            # A move past the right end grows the tape by one zero cell.
            if ptr == len(cells):
                cells = (*cells, 0)
        elif command == "left":
            # ``left`` at the origin is clamped rather than an error.
            ptr = max(0, ptr - 1)
        elif command == "goto":
            ind = target - 2
        elif command == "input":
            cells = (*cells[:ptr], byte or 0, *cells[ptr + 1 :])
    return (ind + 1, ptr, cells)


class _Machine:
    """A BrainIf run: one immutable ``_State``, rebound per step.

    The protocol the rest of the library expects (``step``, ``halted``,
    ``snapshot``, and the ``cells``/``ind``/``ptr`` attributes) is mutable
    by construction, so this class supplies it.  All it does is hold the
    current state and the program; the rules themselves are the pure
    functions above.

    ``step()`` executes one line; ``halted`` is true once the cursor passes
    the last line.  A ``goto`` can rewind the cursor, so a loop whose cell
    never leaves the tested value is a finite-state cycle the state-cycle
    hang detector can prove.
    """

    __slots__ = ("code", "io", "size", "state")

    def __init__(self, code: list[str], io: IO) -> None:
        """Start with a single zero cell at the origin."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per line -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, 0, (0,))

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def cells(self) -> tuple[int, ...]:
        # The state's own tuple, handed back as it stands.  Brainfuck's
        # ``tape`` reads the same way, so the two tape languages agree.
        return self.state[2]

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

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
        return list(self.state[2])

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

        Parsing, the two I/O effects, and the malformed-line rejection are
        all here rather than in the transition: this is the shell, so it is
        where an effect or an error belongs, and it leaves
        :func:`_advance` total.  ``output`` writes and changes no state;
        ``input`` reads and hands the byte to the transition, which stores
        it.

        The I/O only happens when the guard passes, which is why the guard
        is tested here as well -- an ``input`` line whose guard fails must
        not consume a byte.
        """
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
                    # The original skips empty reads rather than storing
                    # one, so a blank input line is not a zero byte.
                    while not (s := self.io.input_str()):
                        pass
                    byte = ord(s[0])
        self.state = _advance(self.state, parsed, byte)


def run(code: list[str], io: IO) -> None:
    """Run a BrainIf program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
