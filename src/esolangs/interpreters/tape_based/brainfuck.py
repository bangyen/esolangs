"""Interpreter for Brainfuck.

The tape is 8-bit wrapping and grows rightward, ``<`` is clamped at the
left edge, and loops are matching-bracket.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and a command to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  The
tape is a tuple, so a state is a value that can be stored, compared, and
hashed as it stands -- ``snapshot`` returns it directly rather than
rebuilding.

:class:`_Machine` is the mutable shell the interpreter protocol requires
(``esolangs.vm`` wraps it, ``run_until_halt_or_cycle`` steps it, and
``factor.py`` drives a decoded program through it).  It holds one
``_State`` and rebinds it each step, so the mutation lives in exactly
one assignment and every rule about what brainfuck *does* stays in the pure
layer.  The one effect a command can have, ``.`` and ``,``'s I/O, is done
by ``step`` before it calls the pure transition -- effects in the shell,
rules in the core.

The brainfuck spec defines ``[``/``]`` only for matched pairs; a program
with unbalanced brackets is malformed, so the interpreter rejects it with a
:class:`ValueError` rather than inventing a halt the language does not
specify.

The spec leaves EOF undefined for ``,`` (returning zero or leaving the cell
unchanged are both suggested); this interpreter instead raises
:class:`EOFError` when input is exhausted, so the classic `,[.,]` cat
program terminates with an error rather than a graceful halt.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.brackets import match_brackets as matches
from esolangs.interpreters.io import IO

#: ``(ind, ptr, tape, acc, dirty)``: an immutable value, rebound per step.
#: ``acc`` is the true cell under the pointer; while ``dirty``, ``tape[ptr]``
#: is stale and :func:`_committed` (every path that leaves the cell) fixes it.
#: One rebuild per run of ``+``/``-`` instead of one per command: 58% of
#: executed commands are ``+``/``-``, in runs averaging 3.8, max 49.
#: ``snapshot`` and ``tape`` commit first, so one logical state has one
#: spelling and the cycle detector's hash sees a repeat as a repeat.
#: A plain tuple: ``NamedTuple.__new__`` is Python-level, 2.7x slower to
#: build, and this is built once per step.  Code and bracket map are
#: parameters, not fields, so the cycle detector stores no constants.
#: Order starts ``ind, ptr, tape`` because ``snapshot`` returns those three.
type _State = tuple[int, int, tuple[int, ...], int, bool]


def _written(tape: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    """Return ``tape`` with cell ``ptr`` set to ``value``.

    The tape is rebuilt around the one changed cell, which is what an
    immutable tape costs.  It stays affordable because the buffer above
    means a run of ``+``/``-`` reaches this once rather than once per
    command, and because a brainfuck tape is the handful of cells a program
    actually touches -- the repo's generated programs run to nine, and
    longer text to eighteen -- not a preallocated array.
    """
    return (*tape[:ptr], value, *tape[ptr + 1 :])


def _committed(state: _State) -> tuple[int, ...]:
    """Return ``state``'s tape with the buffered cell written back if stale.

    The one place the buffer's invariant is discharged.  Every path that
    leaves the cell under the pointer -- a move, and the observers on
    :class:`_Machine` -- goes through here, so no caller has to remember
    what ``dirty`` means.
    """
    _, ptr, tape, acc, dirty = state
    return _written(tape, ptr, acc) if dirty else tape


def _advance(state: _State, code: str, brackets: dict[int, int]) -> _State:
    """Return the state after executing the command at the code position.

    Pure: it reads ``state`` and returns a new one, and every command that
    is not I/O is decided entirely here.  It takes no ``io`` argument, so
    ``.`` and ``,`` are necessarily the caller's business; this function
    sees only what they leave behind -- ``.`` changes no state at all, and
    ``,``'s new cell value arrives already written.

    The fields are unpacked to locals and one state is built at the end,
    rather than each branch deriving a state from the last.  That is a
    measured choice, not a style one: threading the state through
    per-branch rebuilds cost two constructions per step and made the
    interpreter ~5.6x slower than the mutable original, against ~2x for
    building once.

    Anything that is not one of the eight commands is a comment and falls
    through to the shared increment, which is what makes the code position
    advance exactly once per call.
    """
    ind, ptr, tape, acc, dirty = state
    char = code[ind]
    if char == "+":
        # Buffered; the tape is untouched.
        acc = (acc + 1) % 256
        dirty = True
    elif char == "-":
        acc = (acc - 1) % 256
        dirty = True
    elif char == ">":
        # Leaving the cell: commit first.  Past the right end grows by one.
        tape = _committed(state)
        dirty = False
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
        acc = tape[ptr]
    elif char == "<":
        # Clamped at the left edge; a clamped move stays, so no commit.
        if ptr:
            tape = _committed(state)
            dirty = False
            ptr -= 1
            acc = tape[ptr]
    elif (char == "[" and acc == 0) or (char == "]" and acc != 0):
        # Tests ``acc`` (the truth).  Lands on the partner; +1 steps past it.
        ind = brackets[ind]
    return (ind + 1, ptr, tape, acc, dirty)


class _Machine:
    """A Brainfuck run: one immutable ``_State``, rebound per step.

    The protocol the rest of the library expects (``step``, ``halted``,
    ``snapshot``, and the ``ind``/``ptr``/``tape`` attributes ``vm.py``
    reads) is mutable by construction, so this class supplies it.  All it
    does is hold the current state and the two constants a transition
    needs; the rules themselves are the pure functions above.
    """

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = matches(code)
        # ``halted`` is read twice per command; take the length once.
        self.size = len(code)
        self.state: _State = (0, 0, (0,), 0, False)

    # Views for ``factor.py``.  ``tape`` and ``snapshot`` commit first: an
    # observer never sees the stale window (see ``_State``).

    @property
    def tape(self) -> tuple[int, ...]:
        return _committed(self.state)

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def ind(self) -> int:
        return self.state[0]

    def input_position(self) -> int:
        """Report the input cursor for the growth detector.

        ``snapshot`` folds the same number into its tuple; the growth
        certificate needs it on its own, because it compares the cursor
        across two visits rather than hashing a whole state.
        """
        return self.io.position()

    @property
    def halted(self) -> bool:
        return self.state[0] >= self.size

    # VM view.  ``memory`` goes through ``tape``, so it commits too.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Committed tape plus input cursor (a repeat that ignores consumed
        # input is not a cycle).  ``acc``/``dirty`` would give one state two hashes.
        ind, ptr = self.state[0], self.state[1]
        return (ind, ptr, _committed(self.state), self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the code position.

        The two character commands are done here rather than in a function
        of their own: this is the shell, so it is where an effect belongs,
        and it keeps :func:`_advance` reachable in one call per step.
        ``.`` writes and changes no state; ``,`` reads and leaves the byte
        in the cell, so the pure transition then runs on what they left
        behind and never needs the ``io`` object at all.

        Both go through the write buffer rather than the tape: ``acc`` is
        the cell's true value, so printing reads it directly, and a read
        stores into it and marks the tape stale exactly as ``+`` would.
        """
        state = self.state
        if state[0] >= self.size:
            return
        ind, ptr, tape, acc, _dirty = state
        char = self.code[ind]
        if char == ".":
            self.io.print_char(chr(acc))
        elif char == ",":
            # ``input_char`` is a whole code point.  Unreduced, ``,.`` echoed
            # an emoji while ``,+.`` printed ``\x01``.  CVNC does the same.
            state = (ind, ptr, tape, self.io.input_char() % 256, True)
        self.state = _advance(state, self.code, self.brackets)


def run(code: str, io: IO) -> None:
    """Run a Brainfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
