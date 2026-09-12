r"""Interpreter for Suffolk."""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : pointer, the accumulator,.
# : transition below returns a.
# : the tape is a ``tuple`` for.
# :.
# : There is no halted flag:.
# : -- a repeated state or the.
# : so "stopped" is a fact.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : it stores one per step.
type _State = tuple[int, int, int, tuple[int, ...]]


def _advance(state: _State, code: str, byte: int | None = None) -> _State:
    r"""Return the state after executing one command."""
    ind, ptr, acc, tape = state
    sym = code[ind]
    if sym == ">":
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
    elif sym == "<":
        acc += tape[ptr]
        ptr = 0
    elif sym == "!":
        tape = (*tape[:ptr], max(0, tape[ptr] + 1 - acc), *tape[ptr + 1 :])
        ptr = acc = 0
    elif sym == ",":
        acc = byte if byte is not None else 0
    ind += 1
    return (0 if ind == len(code) else ind, ptr, acc, tape)


class _Machine:
    r"""Per-run Suffolk state: the code, tape, and accumulator."""

    # : Whether the program can.
    # : language, not to whoever is.
    # : infinite, so ``while not.
    # : caller stepping this one.
    # : detector, or.
    # :.
    # : :func:`run` stops it from.
    # : program that reads hits.
    # : and one that reads nothing.
    self_halts = False

    def __init__(self, code: str, io: IO) -> None:
        r"""Store ``code`` and start the tape and accumulator at zero."""
        if not code:
            raise ValueError("Suffolk program cannot be empty")
        self.io = io
        self.code = code
        self.state: _State = (0, 0, 0, (0,))
        self._exhausted = False

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def acc(self) -> int:
        return self.state[2]

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[3]

    @property
    def halted(self) -> bool:
        r"""True once a read has run past the end of the input."""
        return self._exhausted

    # ``esolangs.vm._AffineMachine``.
    # Suffolk qualifies because.
    # what to do -- ``ind`` wraps.
    # fixed rules -- and every.
    # one ``max(0, ...)``, which.
    # decides is the one.
    # cells growing without bound,.

    @property
    def key(self) -> tuple[int, int, int]:
        r"""The equality-compared state: cursor, pointer, and tape width."""
        ind, ptr, _acc, tape = self.state
        return (ind, ptr, len(tape))

    @property
    def values(self) -> tuple[int, ...]:
        r"""The unbounded values: the accumulator, then the cells."""
        _ind, _ptr, acc, tape = self.state
        return (acc, *tape)

    @property
    def clamp_slack(self) -> int | None:
        r"""``!``'s clamped quantity before it is clamped, else ``None``."""
        ind, ptr, acc, tape = self.state
        if self.code[ind] != "!":
            return None
        return tape[ptr] + 1 - acc

    def input_position(self) -> int:
        r"""Return the input cursor, so a reading loop is not a repeat."""
        return self.io.position()

    # The VM's language-shaped.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.state[3])

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        ind, ptr, acc, tape = self.state
        return (ind, ptr, acc, tape, self.io.position())

    def step(self) -> None:
        r"""Execute one command, wrapping to the start at the end of the code."""
        if self._exhausted:
            return
        ind, _ptr, acc, _tape = self.state
        sym = self.code[ind]
        byte = None
        if sym == ",":
            # The read past the end of the.
            # so it ends the machine here.
            # happens to be driving.
            # state stays the one that.
            try:
                inp = self.io.input_str()
            except EOFError:
                self._exhausted = True
                return
            byte = acc + ord(inp[0]) if inp else 0
        elif sym == "." and acc:
            self.io.print_char(chr(acc - 1))
        self.state = _advance(self.state, self.code, byte)


def run(code: str, io: IO) -> None:
    r"""Run a Suffolk program until it repeats a state or runs out of input."""
    machine = _Machine(code, io)
    seen: set[tuple[object, ...]] = set()
    while not machine.halted:
        state = machine.snapshot()
        if state in seen:
            return
        seen.add(state)
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
