r"""Interpreter for 123."""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

_READ = -3
_WRITE = -2
_START = 0

# : The set bits of the tape,.
# : unbounded and starts.
# : tape -- there is nothing to.
# :.
# : A frozenset rather than a.
# : tested, set, or cleared;.
# : way out, as it always did,.
type _Bits = frozenset[int]

# : One instant of a run:.
# : tape pointer, the set bits,.
# : a record: every transition.
#: one in place.
# :.
# : ``done`` is state because.
# : check makes, and it depends.
# : the end with the pointer.
# : back to the start.
#: carry it.
# :.
# : ``done`` stays out of.
#: always reported.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : stores.
type _State = tuple[int, int, _Bits, bool]


def _byte_of(bits: _Bits) -> int:
    r"""Read locations 0-7 as an MSB-first byte (location 0 is bit 7)."""
    return sum((1 << (7 - i)) for i in range(8) if i in bits)


def _with_byte(bits: _Bits, value: int) -> _Bits:
    r"""Return ``bits`` with locations 0-7 set from ``value``, MSB-first."""
    return (bits - frozenset(range(8))) | frozenset(
        i for i in range(8) if value & (1 << (7 - i))
    )


def _jump(code: str, ip: int, *, back: bool) -> int:
    r"""Return the cursor after a ``3`` jumps backward or forward."""
    if back:
        j = ip - 1
        while j >= 0 and code[j] != "3":
            j -= 1
    else:
        j = ip + 1
        while j < len(code) and code[j] != "3":
            j += 1
    return j + 1


def _advance(state: _State, code: str, byte: int | None = None) -> _State:
    r"""Return the state after executing one command."""
    ip, pos, bits, done = state
    if ip >= len(code):
        # End of the program: halt.
        return (ip, pos, bits, True) if pos < 0 else (_START, pos, bits, done)
    char = code[ip]
    if char == "1":
        bits = bits ^ frozenset((pos,))
        pos -= 1
        # The pointer wraps from -4.
        if pos == -4:
            pos = _START
    elif char == "2":
        if pos == _READ:
            bits = _with_byte(bits, byte if byte is not None else 0)
            pos = _START
        elif pos == _WRITE:
            pos = _START
        else:
            pos += 1
    elif char == "3" and pos >= 0:
        # Below location 0 a ``3`` is a.
        # jump has already positioned.
        return (_jump(code, ip, back=pos in bits), pos, bits, done)
    return (ip + 1, pos, bits, done)


class _Machine:
    r"""Per-run 123 state: an unbounded bit tape, pointer, and code cursor."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Store ``code`` and reset the tape; a command-less program halts."""
        self.code = code
        self.io = io
        self.n = len(code)
        # A program with no commands.
        idle = not any(c in "123" for c in code)
        self.state: _State = (0, _START, frozenset(), idle)

    # The language's own names.
    # than fields of their own, so.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.state[0]

    @property
    def pos(self) -> int:
        return self.state[1]

    @property
    def bits(self) -> _Bits:
        r"""The locations holding TRUE."""
        return self.state[2]

    def place(self, ip: int, pos: int, bits: frozenset[int] = frozenset()) -> None:
        r"""Put the machine on a given cursor, pointer, and set of TRUE bits."""
        self.state = (ip, pos, bits, self.state[3])

    @property
    def halted(self) -> bool:
        r"""Whether the run has ended (or has no commands to run)."""
        return self.state[3]

    # The VM's language-shaped.
    # cursor.

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.byte()]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The set locations, sorted, as.
        # logical tape must have.
        # detector compares states of a.
        ip, pos, bits, _done = self.state
        return (ip, pos, tuple(sorted(bits)), self.io.position())

    def byte(self) -> int:
        r"""Read locations 0-7 as an MSB-first byte (location 0 is bit 7)."""
        return _byte_of(self.state[2])

    def step(self) -> None:
        r"""Execute one command (or the loop-or-halt check), advancing."""
        ip, pos, bits, done = self.state
        if done:
            return
        byte = None
        if ip < self.n and self.code[ip] == "2":
            if pos == _READ:
                byte = self.io.input_char()
            elif pos == _WRITE:
                self.io.print_char(chr(_byte_of(bits)))
        self.state = _advance(self.state, self.code, byte)


def run(code: str, io: IO) -> None:
    r"""Run a 123 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
