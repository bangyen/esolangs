"""Interpreter for 123.

An unbounded bit tape from location 0.  ``1`` flips the bit and moves
left, wrapping -4 to 0.  ``2`` reads a character into locations 0-7 at
-3, writes them at -2 (both reset the pointer to 0), and otherwise moves
right.  ``3`` is a NOP below 0; on TRUE it jumps back to the previous
``3`` (or the start), on FALSE forward to the next (or the end).  The
program halts only at the end with the pointer below 0, else loops.
Locations 0-7 are MSB-first (location 0 is bit 7), as the cross-checks
and the generator agree, opposite the wiki's little-endian note.
``2`` reads a line's first byte and raises :class:`EOFError` when
exhausted; a program with no commands halts with no output.
:func:`_advance` is pure over an immutable ``_State``; ``2``'s I/O is
the shell's.
"""

from __future__ import annotations

import sys
from functools import lru_cache

from esolangs.interpreters.io import IO

_READ = -3
_WRITE = -2
_START = 0

#: The TRUE locations of an unbounded all-FALSE tape.  A frozenset: order
#: is never read, and ``snapshot`` sorts on the way out.
type _Bits = frozenset[int]

#: ``(ip, pos, bits, done)``: an immutable value, rebound per step.
#: ``done`` is state because the end-of-program check depends on the
#: pointer (below 0 halts, else loops), not the cursor; it stays out of
#: ``snapshot``.  The code is a parameter, not a field.
type _State = tuple[int, int, _Bits, bool]


def _byte_of(bits: _Bits) -> int:
    """Read locations 0-7 as an MSB-first byte (location 0 is bit 7)."""
    return sum((1 << (7 - i)) for i in range(8) if i in bits)


def _with_byte(bits: _Bits, value: int) -> _Bits:
    """Return ``bits`` with locations 0-7 set from ``value``, MSB-first."""
    return (bits - frozenset(range(8))) | frozenset(
        i for i in range(8) if value & (1 << (7 - i))
    )


@lru_cache(maxsize=16)
def _landings(code: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return where a backward and a forward ``3`` jump land, per position.

    Two prefix scans at load (the jump used to walk to its partner each
    time); no ``3`` behind lands at the start, none ahead past the end.
    """
    size = len(code)
    back = [0] * size
    last = -1
    for i in range(size):
        back[i] = last + 1
        if code[i] == "3":
            last = i
    forward = [size + 1] * size
    nxt = size
    for i in range(size - 1, -1, -1):
        forward[i] = nxt + 1
        if code[i] == "3":
            nxt = i
    return tuple(back), tuple(forward)


def _advance(
    state: _State,
    code: str,
    landings: tuple[tuple[int, ...], tuple[int, ...]],
    byte: int | None = None,
) -> _State:
    """Return the state after executing one command.

    The end of the code halts only with the pointer below 0, else the cursor
    returns to the start -- a state decision, so here.  ``3`` places the
    cursor itself.
    """
    ip, pos, bits, done = state
    if ip >= len(code):
        # End of the program: halt below location 0, else loop from the top.
        return (ip, pos, bits, True) if pos < 0 else (_START, pos, bits, done)
    char = code[ip]
    if char == "1":
        bits = bits ^ frozenset((pos,))
        pos -= 1
        # The pointer wraps from -4 back to 0.
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
        # Below location 0 a ``3`` is a NOP; at or above it jumps, and the
        # jump has already positioned the cursor.
        return (landings[0 if pos in bits else 1][ip], pos, bits, done)
    return (ip + 1, pos, bits, done)


class _Machine:
    """Per-run 123 state: an unbounded bit tape, pointer, and code cursor.

    A program touching a bounded prefix always resolves as a cycle; one that
    marches right forever is the detector's unbounded-growth case.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and reset the tape; a command-less program halts."""
        self.code = code
        # Where each jump lands, scanned once rather than per jump.
        self._landings = _landings(code)
        self.io = io
        self.n = len(code)
        # A program with no commands can never move, so it is done already.
        idle = not any(c in "123" for c in code)
        self.state: _State = (0, _START, frozenset(), idle)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def pos(self) -> int:
        return self.state[1]

    @property
    def bits(self) -> _Bits:
        """The locations holding TRUE."""
        return self.state[2]

    def place(self, ip: int, pos: int, bits: frozenset[int] = frozenset()) -> None:
        """Put the machine on a given cursor, pointer, and set of TRUE bits.

        How the backward-jump branch is exercised: no short program reaches it.
        """
        self.state = (ip, pos, bits, self.state[3])

    @property
    def halted(self) -> bool:
        """Whether the run has ended (or has no commands to run)."""
        return self.state[3]

    # The VM's language-shaped view: Unbounded bit tape + pointer; ip is the code
    # cursor.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.byte()]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # A frozenset is already canonical and hashable; sorting it at every
        # cycle probe dominated generated programs.  ``done`` stays out: the
        # detector compares states of a running machine.
        ip, pos, bits, _done = self.state
        return (ip, pos, bits, self.io.position())

    def byte(self) -> int:
        """Read locations 0-7 as an MSB-first byte (location 0 is bit 7)."""
        return _byte_of(self.state[2])

    def step(self) -> None:
        """Execute one command (or the loop-or-halt check), advancing.

        The position is tested here too: a ``2`` elsewhere must not touch I/O.
        """
        ip, pos, bits, done = self.state
        if done:
            return
        byte = None
        if ip < self.n and self.code[ip] == "2":
            if pos == _READ:
                byte = self.io.input_char()
            elif pos == _WRITE:
                self.io.print_char(chr(_byte_of(bits)))
        self.state = _advance(self.state, self.code, self._landings, byte)


def run(code: str, io: IO) -> None:
    """Run a 123 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
