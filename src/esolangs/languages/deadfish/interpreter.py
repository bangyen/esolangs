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

from collections.abc import Callable
from typing import NamedTuple

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

#: The three commands that change the accumulator; ``o`` and ``h`` do not.
_ARITHMETIC: dict[str, Callable[[int], int]] = {
    "i": lambda value: value + 1,
    "d": lambda value: value - 1,
    "s": lambda value: value * value,
}

#: The two values the accumulator is reset from, and the only two.  A range
#: check reads as the intent and is the bug the C comment describes.
_TRAPS = (-1, 256)


class _State(NamedTuple):
    ind: int = 0
    value: int = 0
    stopped: bool = False  # set by ``h``, the only way to stop early


def _advance(state: _State, code: str) -> tuple[_State, str | None]:
    """Return the state after one character, and the text it prints.

    The reset follows every command, so it sits after the dispatch rather
    than inside each arithmetic branch.
    """
    command = code[state.ind]
    if command == "h":
        return state._replace(stopped=True), None
    value = state.value
    if command in _ARITHMETIC:
        value = _ARITHMETIC[command](value)
    if value in _TRAPS:
        value = 0
    return _State(state.ind + 1, value), f"{value}\n" if command == "o" else None


class _Machine:
    """The source, the read position and the one accumulator."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.state = _State()

    @property
    def halted(self) -> bool:
        return self.state.stopped or self.state.ind >= len(self.code)

    @property
    def ind(self) -> int:
        return self.state.ind

    @property
    def value(self) -> int:
        return self.state.value

    @property
    def ip(self) -> int:
        return self.state.ind

    @property
    def memory(self) -> list[int]:
        return [self.state.value]

    def snapshot(self) -> tuple[object, ...]:
        return (self.code, *self.state, self.io.progress())

    def step(self) -> None:
        if self.halted:
            return
        self.state, out = _advance(self.state, self.code)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a Deadfish program, printing a line per ``o``."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
