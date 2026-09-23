"""BIO (Binary IO) interpreter implementation.

Three registers (x, y, z); commands are ``[0|1][O|I][x|y|z]`` triples.
The wiki writes a loop as ``0i{ do something };`` and says every command
ends in ``;``, so a command is a triple *with* its terminator and a
loop-open carries its ``{`` (:data:`_COMMAND`); the page's untested
Thutu sketch strips them, and the prose and examples are followed
instead.  Only ``//`` comments are dropped.  Braces are matched at load,
so an unmatched ``}``, a ``0i`` without ``{`` or any undefined character
raises :class:`ValueError` and the loop stack cannot underflow.
:func:`_advance` is pure and total over an immutable ``_State``; the one
print is the shell's.
"""

from __future__ import annotations

import re

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: ``(ind, reg, stk)``: an immutable value, rebound per step.  Commands
#: are a parameter, not a field.  ``snapshot`` still returns
#: ``(reg, stk, ind, ...)``, the order it always did.
type _State = tuple[int, tuple[int, int, int], tuple[int, ...]]


def _bumped(reg: tuple[int, int, int], index: int, delta: int) -> tuple[int, int, int]:
    """Return ``reg`` with register ``index`` moved by ``delta``."""
    values = list(reg)
    values[index] += delta
    return (values[0], values[1], values[2])


def _closers(commands: list[str]) -> tuple[int, ...]:
    """Return, per command, the ``};`` that closes a loop opened there.

    ``-1`` where nothing opens.  One pass at load: searching per skip made
    Theta(T) skips cost Theta(T) each.
    """
    closes = [-1] * len(commands)
    open_at: list[int] = []
    for ind, command in enumerate(commands):
        if command.endswith("{"):
            open_at.append(ind)
        elif command == "};":
            closes[open_at.pop()] = ind
    return tuple(closes)


# A command is a triple with its ``;``, a ``0i`` triple with its ``{``, or
# ``};`` (the wiki: ``0i{ do something };``, every command ends in ``;``).
# The terminator is bound to the opcode: a blind ``(?:\{|;)`` accepted
# ``0ix;`` (walked off the end in ``_skip``) and ``0ox{`` (popped an empty
# stack); both are now rejected at load.
_COMMAND = re.compile(r"0[iI][xXyYzZ]\{|(?:0[oO]|1[oOiI])[xXyYzZ];|\};")

# Comments run from ``//`` to the end of the line and carry no meaning, so
# they are removed before the program is tokenized.
_COMMENT = re.compile(r"//[^\n]*")


def parse(code: str) -> list[str]:
    """Return ``code``'s commands, lowercased, or raise on a malformed program.

    Comments stripped, then nothing but commands and whitespace may remain;
    the interpreter used to drop what its regex missed, so a typo ran as a
    different program.
    """
    stripped = _COMMENT.sub("", code)
    commands = [match.group().lower() for match in _COMMAND.finditer(stripped)]
    if "".join(commands) != "".join(stripped.lower().split()):
        raise ValueError("BIO: not a command")
    depth = 0
    for command in commands:
        if command.endswith("{"):
            depth += 1
        elif command == "};":
            if not depth:
                raise ValueError("BIO: '}' closes no loop")
            depth -= 1
    if depth:
        raise ValueError("BIO: unmatched '{'")
    return commands


class _Machine:
    """Per-run BIO state: the registers, the loop stack, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into commands and reset the registers."""
        self.io = io
        self.commands = parse(code)
        # Where each loop ends, matched once here rather than searched for
        # on every zero-register exit.
        self.closes = _closers(self.commands)
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.commands)
        self.state: _State = (0, (0, 0, 0), ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def reg(self) -> tuple[int, int, int]:
        """The three registers, x then y then z."""
        return self.state[1]

    @property
    def stk(self) -> tuple[int, ...]:
        """The loop-return stack."""
        return self.state[2]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the command list."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Registers + loop stack + cursor; ip the cursor,
    # memory the regs.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.state[1])

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.state[2])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Both stores are already tuples, in the order this returned before
        # the fields moved into a state value.
        ind, reg, stk = self.state
        return (reg, stk, ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        The one print is here; nothing can fail after the load check.
        """
        ind, reg, _stk = self.state
        if ind >= self.size:
            return
        command = self.commands[ind]
        if command[:2] == "1i":
            # Handle negative values by converting to unsigned 8-bit
            self.io.print_char(chr(reg["xyz".find(command[2])] % 256))
        self.state = _advance(self.state, self.commands, self.closes)


def _advance(state: _State, commands: list[str], closes: tuple[int, ...]) -> _State:
    """Return the state after executing one command.

    ``closes`` is :func:`_closers`.  A ``};`` returns to one before its
    opener, so the shared increment lands back on it and re-tests.
    """
    ind, reg, stk = state
    command = commands[ind]
    # A loop-open command carries the ``{`` that opens its body, so the
    # register is the triple's own last letter rather than the token's.
    r = "xyz".find(command[2]) if command != "};" else -1
    code = command[:2]

    if code == "0o":
        reg = _bumped(reg, r, 1)
    elif code == "1o":
        reg = _bumped(reg, r, -1)
    elif code == "1i":
        pass  # the print already happened in the shell
    elif command == "};":
        ind, stk = stk[-1] - 1, stk[:-1]
    elif reg[r]:
        stk = (*stk, ind)
    else:
        ind = closes[ind]
    return (ind + 1, reg, stk)


def run(code: str, io: IO) -> None:
    """Execute BIO code and produce output."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
