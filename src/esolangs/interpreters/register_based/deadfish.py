"""Interpreter for Deadfish.

Jonathan Todd Skinner's 1999 language, and the first entry here kept for its
fame alone: one accumulator and four commands -- ``i`` increments, ``d``
decrements, ``s`` squares, ``o`` prints the value as a decimal number.  There
is no character output and, famously, no input vocabulary at all, so no
boolean generator can exist for it and the registry carries none; ``esolangs
list --details`` marks it ``int``.

The arithmetic is the whole joke.  After *every* command the accumulator resets
to 0 if and only if it equals ``-1`` or ``256`` -- not "greater than 256", which
is what the C original's own comment claims -- so ``iissso`` prints 0 by landing
on 256 exactly while ``diissisdo`` prints 288, 289 sailing past untouched.  The
wiki calls those cases mandatory, and they are asserted as such.

Two decisions, both spelled out by the page rather than gaps in it.  A
character that is not a command is ignored: "anything that is not a command is
not accepted" and "errors are not acknowledged", so a Deadfish program cannot
be malformed and no :class:`ValueError` is raised from here -- unusually for
this package, and deliberately.  And ``h``, which the command table carries as
"(optional)", halts; it is honoured, since a table entry is a weaker thing to
ignore than to support.

Each ``o`` writes the number and a newline: the wiki's shell transcript puts one
value per line, and without a separator a program printing 1 then 2 reads the
same as one printing 12.  Nothing is read and no operation can be invalid, so
neither ``EOFError`` nor :class:`~esolangs.exceptions.HaltError` arises.
"""

from __future__ import annotations

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: ``(ind, value)``: the code position and the one accumulator.
type _State = tuple[int, int]

#: The two values the accumulator is reset from, and the only two.  A range
#: check reads as the intent and is the bug the C comment describes.
_TRAPS = (-1, 256)


def _advance(state: _State, code: str) -> tuple[_State, str | None]:
    """Return the state after one command, and the text to print.

    Pure.  The reset is applied to whatever the command left behind, which is
    why it belongs here and not in the three arithmetic branches.
    """
    ind, value = state
    command = code[ind]
    if command == "i":
        value += 1
    elif command == "d":
        value -= 1
    elif command == "s":
        value *= value
    if value in _TRAPS:
        value = 0
    out = f"{value}\n" if command == "o" else None
    return (ind + 1, value), out


class _Machine:
    """Per-run state: the code position and the accumulator."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.state: _State = (0, 0)
        #: Set by ``h``, which is the only way to stop before the end.
        self.stopped = False

    @property
    def ind(self) -> int:
        """The code position."""
        return self.state[0]

    @property
    def value(self) -> int:
        """The accumulator."""
        return self.state[1]

    @property
    def halted(self) -> bool:
        """Whether the code has run out, or ``h`` has stopped it."""
        return self.stopped or self.state[0] >= len(self.code)

    @property
    def ip(self) -> int:
        """The code position, which is an offset into the source."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The accumulator, as the one cell there is."""
        return [self.state[1]]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.code, *self.state, self.stopped, self.io.position())

    def step(self) -> None:
        """Execute one character, printing when it is an ``o``."""
        if self.halted:
            return
        if self.code[self.state[0]] == "h":
            self.stopped = True
            return
        self.state, out = _advance(self.state, self.code)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a Deadfish program, printing a line per ``o``."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
