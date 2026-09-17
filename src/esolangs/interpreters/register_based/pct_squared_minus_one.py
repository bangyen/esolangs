"""Interpreter for %^2^-1.

One accumulator holding the magnitude ``x`` of ``10^x`` (starts 0).
``s``/``i`` subtract 2/3, ``m`` doubles, ``p`` negates, ``'`` zeroes,
``l``/``e`` print (decimal / low byte), ``n`` reads one byte, ``t``
rewinds to the start when nonzero (the only loop).  The magnitude is
reset to zero before each command when it exceeds 3003.  ``n`` raises
:class:`EOFError` on exhausted input (the cross-check exits 3).
:func:`_advance` is pure over ``(ind, acc)``, which ``snapshot`` returns
directly; the shell does the three I/O commands.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: ``(ind, acc)``: an immutable value, rebound per step, and exactly what
#: ``snapshot`` returns.  The code is a parameter, not a field.
type _State = tuple[int, int]


def _reset(state: _State) -> _State:
    """Return ``state`` with an over-3003 accumulator zeroed.

    The single definition; the shell's prints use it too.
    """
    ind, acc = state
    return (ind, 0) if acc > 3003 else state


def _advance(state: _State, code: str) -> _State:
    """Return the state after executing the command at the code position.

    Pure; ``n``'s byte arrives in the accumulator.  The reset applies
    *before* the command (``m`` on 4000 doubles 0).  ``t`` on nonzero rewinds
    to position 0 rather than falling through to the increment.
    """
    ind, acc = _reset(state)
    char = code[ind]
    if char == "s":
        acc -= 2
    elif char == "i":
        acc -= 3
    elif char == "m":
        acc *= 2
    elif char == "p":
        acc *= -1
    elif char == "'":
        acc = 0
    elif char == "t" and acc != 0:
        # The rewind lands on position 0 and is read from there next step,
        # so it returns directly rather than taking the increment below.
        return (0, acc)
    return (ind + 1, acc)


class _Machine:
    """A %^2^-1 run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start the accumulator at zero."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here
        # rather than recomputed on every one of those reads.
        self.size = len(code)
        self.state: _State = (0, 0)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def acc(self) -> int:
        return self.state[1]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Accumulator + cursor; ip the cursor, memory the
    # accumulator.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.state[1]]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The state as it stands: it is already the (ind, acc) pair this
        # returned before the split, and it is already hashable.
        return self.state

    def step(self) -> None:
        """Execute one command, resetting the accumulator first if too large.

        The prints report the reset accumulator, through :func:`_reset`.
        """
        if self.state[0] >= self.size:
            return
        state = _reset(self.state)
        ind, acc = state
        char = self.code[ind]
        if char == "l":
            self.io.print_num(acc)
        elif char == "e":
            self.io.print_char(chr(acc & 0xFF))
        elif char == "n":
            state = (ind, self.io.input_char())
        self.state = _advance(state, self.code)


def run(code: str, io: IO) -> None:
    """Run a %^2^-1 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
