r"""BIO (Binary IO) interpreter implementation."""

from __future__ import annotations

import re
import sys

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : three registers, and the.
# : every transition below.
# : place, and both stores are.
# :.
# : The commands are.
# : run, so carrying them would.
# : detector stores.
# :.
# : The field order starts.
# : series, but ``snapshot``.
#: order it always returned.
type _State = tuple[int, tuple[int, int, int], tuple[int, ...]]


def _bumped(reg: tuple[int, int, int], index: int, delta: int) -> tuple[int, int, int]:
    r"""Return ``reg`` with register ``index`` moved by ``delta``."""
    values = list(reg)
    values[index] += delta
    return (values[0], values[1], values[2])


def _skip(commands: list[str], ind: int) -> int:
    r"""Return the index of the ``};`` closing the loop opened at ``ind``."""
    mat = 1
    while mat:
        ind += 1
        if commands[ind].endswith("{"):
            mat += 1
        elif commands[ind] == "};":
            mat -= 1
    return ind


# A BIO command: an.
# loop-open triple carrying the.
# that closes one.
# says every command is ended.
# rather than being.
# either is not a command at.
# .
# The terminator is bound to.
# ``0i`` takes ``{``, and every.
# ``(?:\{|;)`` accepted the two.
# walked off the end at run.
# ``};`` that brace matching.
# nothing had pushed, so its.
# rejected at load, which is.
_COMMAND = re.compile(r"0[iI][xXyYzZ]\{|(?:0[oO]|1[oOiI])[xXyYzZ];|\};")

# Comments run from ``//`` to.
# they are removed before the.
_COMMENT = re.compile(r"//[^\n]*")


def parse(code: str) -> list[str]:
    r"""Return ``code``'s commands, lowercased, or raise on a malformed."""
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
    r"""Per-run BIO state: the registers, the loop stack, and the cursor."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Parse ``code`` into commands and reset the registers."""
        self.io = io
        self.commands = parse(code)
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(self.commands)
        self.state: _State = (0, (0, 0, 0), ())

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def reg(self) -> tuple[int, int, int]:
        r"""The three registers, x then y then z."""
        return self.state[1]

    @property
    def stk(self) -> tuple[int, ...]:
        r"""The loop-return stack."""
        return self.state[2]

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the command list."""
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # memory the regs.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.state[1])

    @property
    def stack(self) -> list[object]:
        r"""The stack."""
        return list(self.state[2])

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # Both stores are already.
        # the fields moved into a state.
        ind, reg, stk = self.state
        return (reg, stk, ind, self.io.position())

    def step(self) -> None:
        r"""Execute one command, advancing the cursor."""
        ind, reg, _stk = self.state
        if ind >= self.size:
            return
        command = self.commands[ind]
        if command[:2] == "1i":
            # Handle negative values by.
            self.io.print_char(chr(reg["xyz".find(command[2])] % 256))
        self.state = _advance(self.state, self.commands)


def _advance(state: _State, commands: list[str]) -> _State:
    r"""Return the state after executing one command."""
    ind, reg, stk = state
    command = commands[ind]
    # A loop-open command carries.
    # register is the triple's own.
    r = "xyz".find(command[2]) if command != "};" else -1
    code = command[:2]

    if code == "0o":
        reg = _bumped(reg, r, 1)
    elif code == "1o":
        reg = _bumped(reg, r, -1)
    elif code == "1i":
        pass  # the print already happened in.
    elif command == "};":
        ind, stk = stk[-1] - 1, stk[:-1]
    elif reg[r]:
        stk = (*stk, ind)
    else:
        ind = _skip(commands, ind)
    return (ind + 1, reg, stk)


def run(code: str, io: IO) -> None:
    r"""Execute BIO code and produce output."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
