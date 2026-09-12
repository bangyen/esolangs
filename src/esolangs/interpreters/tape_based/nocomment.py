r"""Interpreter for NoComment."""

from __future__ import annotations

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The default static tape size.
# want of an unbounded Python.
# legal and defines them as.
# outright that "this is the.
# tape with no opposite end.
# not an option -- only which.
# .
# The wiki leaves the size.
# their own.
# steps left to ``tape - 1``,.
# wrapping programs do.
_TAPE = 4096

# : One instant of a run:.
# : cursor, the pointer, the.
# : under the pointer.
# : a new one rather than.
#: tuples for the same reason.
# :.
# : The buffer is not.
# : affordable.
# : because the wiki defines.
# : -- so rebuilding it costs.
# : corpus writes the same cell.
# : the current cell and.
# : rebuilds into one.
# : -- whose writes are all to.
# : absorb nothing -- the.
# :.
# : The tape is ``bytes``.
# : collapses *runs*, and the.
# : cell and immediately moves,.
# : corpus commits on almost.
# : ``bytes`` rebuild is one.
# : commits an 11-input decode.
# : the widest generated tables.
# : construction, so ``bytes``.
# : and hashable, which is what.
# :.
# : ``acc`` always holds the.
# : ``dirty`` is set,.
# : tape is brought up to date.
# : leaves the cell goes.
# : outside: ``snapshot`` and.
# : logical state has exactly.
#: equal to itself.
type _State = tuple[int, int, bytes, tuple[int, ...], int, bool]


def _committed(state: _State) -> bytes:
    r"""Return ``state``'s tape with the buffered cell written back if."""
    _ind, ptr, tape, _stack, acc, dirty = state
    if not dirty:
        return tape
    return tape[:ptr] + bytes((acc,)) + tape[ptr + 1 :]


def _advance(state: _State, code: str, size: int) -> _State:
    r"""Return the state after executing the command at the cursor."""
    ind, ptr, tape, stack, acc, dirty = state
    char = code[ind]
    if char == "i":
        # The buffered cell absorbs the.
        acc = (acc + 1) % 256
        dirty = True
    elif char == "d":
        acc = (acc - 1) % 256
        dirty = True
    elif char == "c":
        acc = 0
        dirty = True
    elif char in "lr":
        # Leaving the cell, so the.
        # wraps at both ends, per the.
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
    r"""Per-run NoComment state: the byte tape, the stack, and the cursor."""

    def __init__(self, code: str, io: IO, tape: int = _TAPE) -> None:
        r"""Start with a cleared tape of ``tape`` cells at the origin."""
        if tape < 1:
            raise ValueError(f"the NoComment tape needs at least one cell, got {tape}")
        self.io = io
        self.code = code
        self.size = tape
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.length = len(code)
        self.state: _State = (0, 0, bytes(tape), (), 0, False)

    # The language's own names.
    # than fields of their own, so.
    # .
    # ``tape`` and ``snapshot``.
    # an observer never sees the.

    @property
    def tape(self) -> tuple[int, ...]:
        # The state carries `bytes`;.
        # the widening happens here at.
        # path.
        # transition needs the tuple.
        return tuple(_committed(self.state))

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
        r"""Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.length

    # The VM's language-shaped.

    @property
    def ip(self) -> int:
        r"""The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""The tape's cells."""
        return list(self.tape)

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The committed tape, not the.
        # what this returns, and a.
        # and committed) would make a.
        # .
        # It carries the `bytes`.
        # tuple `tape` reports.
        # is hashable and complete, and.
        # value, so a repeat is still.
        # 4096 cells on every step.
        # whole buffer exists to avoid.
        ind, ptr, _tape, stack, _acc, _dirty = self.state
        return (_committed(self.state), stack, ptr, ind, self.io.position())

    def step(self) -> None:
        r"""Execute one command, advancing the cursor."""
        if self.halted:
            return
        ind, _ptr, _tape, stack, acc, _dirty = self.state
        char = self.code[ind]
        if char == "f" and not stack:
            raise HaltError(
                f"'f' at position {ind} pops the stack and the stack is empty"
            )
        if char in "sb" and acc and stack:
            # ``s`` skips X forward and.
            # command is at ind ± X + 1.
            # half of the bound is dead in.
            # target is always at least 1,.
            # reaches the end -- so.
            # branches behind.
            delta = stack[-1] if char == "s" else -stack[-1]
            if not 0 <= ind + delta + 1 < self.length:
                raise HaltError(
                    f"{char!r} at position {ind} jumps {delta:+d} to "
                    f"{ind + delta + 1}, outside the program's 0..{self.length - 1}"
                )
        elif char == "o":
            self.io.print_char(chr(acc))
        elif char not in "idclrnfsb":
            raise ValueError(f"unrecognized NoComment command {char!r}")
        self.state = _advance(self.state, self.code, self.size)


def run(code: str, io: IO, tape: int = _TAPE) -> None:
    r"""Run a NoComment program on a tape of ``tape`` cells."""
    machine = _Machine(code, io, tape)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
