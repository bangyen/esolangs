"""Interpreter for NoComment.

The full wiki language (not a subset): a byte tape with a movable pointer,
plus a byte stack.  ``i``/``d`` increment/decrement the current cell, ``c``
clears it, ``l``/``r`` move the pointer left/right, ``n`` pushes the current
cell onto the stack, ``f`` pops the stack into the current cell, ``s``/``b``
jump forward/backward by a peeked stack value when the current cell is
nonzero (``s`` skips X instructions, ``b`` jumps back X-1), and ``o`` prints
the current cell as a byte.  The tape is static and the pointer wraps at both
ends (per the wiki, pointer overflow is legal and moves to the opposite end).
Its size defaults to 4096, matching the RISC-V cross-check, and ``run`` takes
a ``tape`` argument for programs that need a longer one.

Per the wiki, any character that is not a command is an error (there are no
comments), and popping an empty stack is an error.  A malformed program
(unrecognized character) raises :class:`ValueError`; an invalid operation
(stack underflow) raises :class:`~esolangs.exceptions.HaltError`.

The interpreter runs on a :class:`_Machine` (the byte tape, the stack, and
the code cursor), so it is step-capable: ``step()`` executes one command and
``halted`` is true once the cursor reaches the end of the code.  A jump back
to a command that never changes state is a cycle the state-cycle hang
detector proves; the ``run()`` backstop stays for the unbounded-growth class.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and a command to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what NoComment *does* stays in
the pure layer.  Printing, and the two errors a program can raise, stay in
the shell -- which is what leaves the transition total.
"""

from __future__ import annotations

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The default static tape size.  The tape is finite by specification, not for
# want of an unbounded Python list: the wiki makes pointer overflow and underflow
# legal and defines them as moving "to the opposite end of memory", then says
# outright that "this is the reason why the memory space needs to be static".  A
# tape with no opposite end could not implement that wrap, so no size at all is
# not an option -- only which finite size.
#
# The wiki leaves the size open, so it is a host choice, and callers may pass
# their own.  The default stays 4096 (matching the RISC-V cross-check's buffer)
# because the size is *observable*: cell 0 steps left to ``tape - 1``, so moving
# the default would change what existing wrapping programs do.
_TAPE = 4096

#: One instant of a run: ``(ind, ptr, tape, stack, acc, dirty)`` -- the code
#: cursor, the pointer, the tape, the stack, and a write buffer for the cell
#: under the pointer.  A value, not a record: every transition below returns
#: a new one rather than editing one in place, and the tape and stack are
#: tuples for the same reason.
#:
#: The buffer is not decoration here, it is what makes the immutable tape
#: affordable.  NoComment's tape is *static* -- 4096 cells by specification,
#: because the wiki defines pointer overflow as wrapping to the opposite end
#: -- so rebuilding it costs the whole 4096 on every write, measured ~470x a
#: list assignment.  The generated corpus writes the same cell 111 times in a
#: row before moving, so buffering the current cell and committing it on a
#: move turns that run of 111 rebuilds into one.  (This is exactly
#: brainfuck's buffer, and unlike RAM0 -- whose writes are all to *different*
#: addresses, where a buffer would absorb nothing -- the pattern here fits.)
#:
#: ``acc`` always holds the true value of the cell under the pointer.  While
#: ``dirty`` is set, ``tape[ptr]`` is stale and ``acc`` is the truth; the
#: tape is brought up to date by :func:`_committed`, which every path that
#: leaves the cell goes through.  The stale window is invisible from
#: outside: ``snapshot`` and the ``tape`` property both commit first, so one
#: logical state has exactly one spelling and a real repeat still compares
#: equal to itself.
type _State = tuple[int, int, tuple[int, ...], tuple[int, ...], int, bool]


def _committed(state: _State) -> tuple[int, ...]:
    """Return ``state``'s tape with the buffered cell written back if stale.

    The one place the buffer's invariant is discharged.  Every path that
    leaves the cell under the pointer -- the two moves, and the observers on
    :class:`_Machine` -- goes through here.
    """
    _ind, ptr, tape, _stack, acc, dirty = state
    if not dirty:
        return tape
    return (*tape[:ptr], acc, *tape[ptr + 1 :])


def _advance(state: _State, code: str, size: int) -> _State:
    """Return the state after executing the command at the cursor.

    Pure, and total: the shell has already rejected the stack underflow, the
    out-of-range jump, and the unrecognized character, so every command it
    can be handed has a defined successor state.  It takes no ``io``
    argument, so ``o``'s print is the caller's business -- it changes no
    state at all.

    ``s`` skips X forward and ``b`` jumps back X-1, which is the same move
    in opposite directions.  Both read the top of the stack without popping
    it, and both only fire when the current cell is nonzero.
    """
    ind, ptr, tape, stack, acc, dirty = state
    char = code[ind]
    if char == "i":
        # The buffered cell absorbs the write; the tape is not touched.
        acc = (acc + 1) % 256
        dirty = True
    elif char == "d":
        acc = (acc - 1) % 256
        dirty = True
    elif char == "c":
        acc = 0
        dirty = True
    elif char in "lr":
        # Leaving the cell, so the buffer is discharged first.  The pointer
        # wraps at both ends, per the wiki.
        tape = _committed(state)
        dirty = False
        ptr = (ptr + (1 if char == "r" else -1)) % size
        acc = tape[ptr]
    elif char == "n":
        stack = (*stack, acc)
    elif char == "f":
        acc, stack = stack[-1], stack[:-1]
        dirty = True
    elif char in "sb" and acc and stack:
        ind += stack[-1] if char == "s" else -stack[-1]
    return (ind + 1, ptr, tape, stack, acc, dirty)


class _Machine:
    """Per-run NoComment state: the byte tape, the stack, and the cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object.
    """

    def __init__(self, code: str, io: IO, tape: int = _TAPE) -> None:
        """Start with a cleared tape of ``tape`` cells at the origin."""
        if tape < 1:
            raise ValueError(f"the NoComment tape needs at least one cell, got {tape}")
        self.io = io
        self.code = code
        self.size = tape
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.length = len(code)
        self.state: _State = (0, 0, (0,) * tape, (), 0, False)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.
    #
    # ``tape`` and ``snapshot`` commit the write buffer before reporting, so
    # an observer never sees the stale window.

    @property
    def tape(self) -> tuple[int, ...]:
        return _committed(self.state)

    @property
    def stack(self) -> tuple[int, ...]:
        return self.state[3]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.length

    # The VM's language-shaped view: cell tape + stack + cursor.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The tape's cells."""
        return list(self.tape)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The committed tape, not the raw one: the cycle detector hashes
        # what this returns, and a logical state with two spellings (dirty
        # and committed) would make a real repeat look like a new state.
        ind, ptr, _tape, stack, _acc, _dirty = self.state
        return (_committed(self.state), stack, ptr, ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        The print and both error cases live here rather than in the
        transition: this is the shell, so it is where an effect or a raise
        belongs, and it leaves :func:`_advance` total.

        ``o`` reads the write buffer rather than the tape, because ``acc``
        is the cell's true value whether or not the tape has caught up.
        """
        if self.halted:
            return
        ind, _ptr, _tape, stack, acc, _dirty = self.state
        char = self.code[ind]
        if char == "f" and not stack:
            raise HaltError
        if char in "sb" and acc and stack:
            # ``s`` skips X forward and ``b`` jumps back X-1: the next
            # command is at ind ± X + 1.  Kept as one check because each
            # half of the bound is dead in one direction -- a forward
            # target is always at least 1, and a backward one rarely
            # reaches the end -- so separate copies leave unreachable
            # branches behind.
            delta = stack[-1] if char == "s" else -stack[-1]
            if not 0 <= ind + delta + 1 < self.length:
                raise HaltError
        elif char == "o":
            self.io.print_char(chr(acc))
        elif char not in "idclrnfsb":
            raise ValueError(f"unrecognized NoComment command {char!r}")
        self.state = _advance(self.state, self.code, self.size)


def run(code: str, io: IO, tape: int = _TAPE) -> None:
    """Run a NoComment program on a tape of ``tape`` cells."""
    machine = _Machine(code, io, tape)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
