"""Interpreter for Tiangou.

A program is one line of single-character commands separated by spaces,
run left to right over a stack of unbounded integers.  ``<`` names the
current position after a popped integer, and ``>`` jumps back to a named
position.  The run halts when the pointer passes the last command.

Commands:
    ``p``  push 1
    ``q``  push -1
    ``i``  push the next input integer
    ``o``  pop and print the value
    ``-``  pop A, then B; push A - B
    ``!``  pop A; push A! if A is positive, else -((-A)!)
    ``"``  swap the top two
    ``:``  duplicate the top
    ``<``  pop A; the A-marker becomes the position after this ``<``
    ``>``  pop A; jump to the A-marker, a no-op if none is set

Input/output:
    ``i`` reads one whitespace-delimited integer; ``o`` writes the value's
    decimal digits with no separator.

Errors:
    ProgramError: a token that is not one of the ten commands.
    InputExhaustedError: ``i`` at EOF.
    ArgumentError: ``i`` given a token that is not an integer.
    HaltError: a pop from an empty stack.

Decisions:
    * A marker resumes *after* its ``<``.  The page's truth machine
      ``i p < : : o >`` loops on input 1 only so: resuming at the ``<``
      would pop the last 1 and leave ``:`` an empty stack.
    * ``-`` pushes top minus second: the page pops A first.
    * ``!`` of 0 is -1: 0 is not positive, so the page's ``-((-A)!)``
      applies.
    * Any whitespace separates commands, so a line break is a space; the
      page's programs are one line.
    * A re-set marker moves to the newer ``<``; the page names one location
      per marker.
"""

from __future__ import annotations

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: Values each command pops before it runs.
_POPS = {"o": 1, "-": 2, "!": 1, '"': 2, ":": 1, "<": 1, ">": 1}
_COMMANDS = frozenset('pqio-!":<>')

type _State = tuple[int, tuple[int, ...]]


def _factorial(value: int) -> int:
    """Return ``value!`` for positive values, else ``-((-value)!)``."""
    result = 1
    for k in range(2, abs(value) + 1):
        result *= k
    return result if value > 0 else -result


def _advance(
    state: _State,
    tokens: tuple[str, ...],
    read: int | None = None,
    target: int | None = None,
) -> tuple[_State, int | None, tuple[int, int] | None]:
    """Return the state after one command, its output and its marker write.

    Pure: the shell passes a read as ``read`` and the ``>`` marker's
    position as ``target``; a ``<`` returns ``(key, position)`` for the
    shell to record.
    """
    ind, stack = state
    c = tokens[ind]
    ind += 1
    out = mark = None
    if c == "p":
        stack = (*stack, 1)
    elif c == "q":
        stack = (*stack, -1)
    elif c == "i" and read is not None:
        stack = (*stack, read)
    elif c == "o":
        out, stack = stack[-1], stack[:-1]
    elif c == "-":
        stack = (*stack[:-2], stack[-1] - stack[-2])
    elif c == "!":
        stack = (*stack[:-1], _factorial(stack[-1]))
    elif c == '"':
        stack = (*stack[:-2], stack[-1], stack[-2])
    elif c == ":":
        stack = (*stack, stack[-1])
    elif c == "<":
        mark, stack = (stack[-1], ind), stack[:-1]
    elif c == ">":
        stack = stack[:-1]
        if target is not None:
            ind = target
    return (ind, stack), out, mark


class _Machine:
    """The run state: the command index, the stack and the markers."""

    # ``ind`` indexes the space-separated commands, not source characters.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        tokens = tuple(code.split())
        for token in tokens:
            if token not in _COMMANDS:
                raise syntax_error(
                    f"unknown command {token!r}",
                    'use p q i o - ! " : < >, one character each, separated by spaces',
                )
        self.tokens = tokens
        self.io = io
        self.state: _State = (0, ())
        # Mutable and shell-owned: a frozen copy per ``<`` would rebuild a
        # map that grows to one entry per marked table row.
        self.markers: dict[int, int] = {}

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.tokens)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, tuple(sorted(self.markers.items())), self.io.progress())

    def step(self) -> None:
        """Run one command; reads, writes and marker lookups happen here."""
        if self.halted:
            return
        ind, stack = self.state
        c = self.tokens[ind]
        if len(stack) < _POPS.get(c, 0):
            raise HaltError(
                f"{c!r} at command {ind} needs {_POPS[c]} value(s) and the "
                f"stack holds {len(stack)}",
                hint="push enough values before popping",
            )
        read = self.io.input_num() if c == "i" else None
        target = self.markers.get(stack[-1]) if c == ">" else None
        self.state, out, mark = _advance(self.state, self.tokens, read, target)
        if mark is not None:
            self.markers[mark[0]] = mark[1]
        if out is not None:
            self.io.print_num(out)


def run(code: str, io: IO) -> None:
    """Run a Tiangou program until the pointer passes its last command."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
