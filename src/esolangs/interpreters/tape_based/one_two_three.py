"""Interpreter for 123.

A bit-tape language: the pointer starts at location 0 over an unbounded
array of bits (all initially FALSE, indexed 0, 1, 2, ... to the right, with
no upper bound).  ``1`` flips the current bit and moves the pointer left,
wrapping from -4 back to 0.  ``2`` reads a character into locations 0-7 when
the pointer is at -3, writes locations 0-7 as a character when at -2 (both
then reset the pointer to 0), and otherwise just moves the pointer right.
``3`` is a jump symbol: below location 0 it is a NOP; otherwise, when the
current bit is TRUE the pointer skips back to the previous ``3`` (or the
start), and when FALSE it skips forward to the next ``3`` (or the end).  The
program halts only when the end is reached with the pointer below 0
(otherwise it loops from the start), and unrecognized characters are NOPs.

Locations 0-7 are read as an 8-bit character MSB-first (location 0 is bit
7): the cross-check interpreters and the repository's generator agree on
this order, which is the opposite of the wiki's little-endian note.

Decisions for gaps in the wiki spec (documented):
- ``,`` reads a whole input line and takes its first byte, raising
  :class:`EOFError` when input runs out (like the other tape interpreters);
- a ``3`` with no next ``3`` skips to the end, where the normal loop-or-halt
  check applies;
- a program with no ``1``/``2``/``3`` commands halts with no output (the
  spec would loop forever on the empty program).

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the code to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what 123 *does* stays in the
pure layer.  The two effects ``2`` can have -- reading a byte at location
-3 and writing one at -2 -- are done by ``step`` before it calls the pure
transition.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

_READ = -3
_WRITE = -2
_START = 0

#: The set bits of the tape, as a frozenset of locations.  The tape is
#: unbounded and starts all-FALSE, so the set of TRUE locations *is* the
#: tape -- there is nothing to preallocate and nothing to grow.
#:
#: A frozenset rather than a sorted tuple because a location is only ever
#: tested, set, or cleared; order is never read.  ``snapshot`` sorts on the
#: way out, as it always did, so one logical tape still has one hash.
type _Bits = frozenset[int]

#: One instant of a run: ``(ip, pos, bits, done)`` -- the code cursor, the
#: tape pointer, the set bits, and whether the run has ended.  A value, not
#: a record: every transition below returns a new one rather than editing
#: one in place.
#:
#: ``done`` is state because halting here is a decision the end-of-program
#: check makes, and it depends on the *pointer*, not the cursor: reaching
#: the end with the pointer below 0 halts, and with it at 0 or above loops
#: back to the start.  The same cursor means either, so the position cannot
#: carry it.
#:
#: ``done`` stays out of ``snapshot``, which reports the four fields it
#: always reported.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[int, int, _Bits, bool]


def _byte_of(bits: _Bits) -> int:
    """Read locations 0-7 as an MSB-first byte (location 0 is bit 7)."""
    return sum((1 << (7 - i)) for i in range(8) if i in bits)


def _with_byte(bits: _Bits, value: int) -> _Bits:
    """Return ``bits`` with locations 0-7 set from ``value``, MSB-first."""
    return (bits - frozenset(range(8))) | frozenset(
        i for i in range(8) if value & (1 << (7 - i))
    )


def _jump(code: str, ip: int, *, back: bool) -> int:
    """Return the cursor after a ``3`` jumps backward or forward.

    Backward lands just after the previous ``3`` (or at the start); forward
    lands just after the next ``3`` (or past the end, where the normal
    loop-or-halt check applies).  Both are total -- a missing partner is
    not an error here, it just runs to the edge.
    """
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
    """Return the state after executing one command.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so ``2``'s read and write are the caller's business -- the
    write changes no state beyond the pointer, and the read's byte arrives
    as ``byte``, already read.

    Reaching the end of the code is not automatically a halt: with the
    pointer below 0 the run ends, and otherwise the cursor returns to the
    start.  That check is here rather than in the shell because it decides
    a state, not an effect.

    ``3`` returns early because its jump already places the cursor; every
    other command falls through to the shared increment.
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
        return (_jump(code, ip, back=pos in bits), pos, bits, done)
    return (ip + 1, pos, bits, done)


class _Machine:
    """Per-run 123 state: an unbounded bit tape, pointer, and code cursor.

    ``step()`` executes one command and ``halted`` says whether the program
    ended — the shape the VM wrapper and the state-cycle hang detector
    expect.  :meth:`snapshot` returns the cursor, pointer, tape contents,
    and input cursor, so a repeated snapshot proves a deterministic run
    loops forever; programs that only ever touch a bounded prefix of the
    tape are bounded-state and always resolve as a cycle, while a program
    that marches the pointer right forever grows the tape without repeating
    a state (the state-cycle detector's documented "unbounded growth" case,
    left to the caller's timeout backstop).
    """

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and reset the tape; a command-less program halts."""
        self.code = code
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

        A caller can reach a state directly rather than running a program
        up to it, which is how the backward-jump branch is exercised: no
        short program both sets a bit at a location and arrives on a ``3``
        with an earlier ``3`` behind it.
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
        # The set locations, sorted, as this always reported them -- one
        # logical tape must have exactly one hash.  ``done`` stays out: the
        # detector compares states of a running machine.
        ip, pos, bits, _done = self.state
        return (ip, pos, tuple(sorted(bits)), self.io.position())

    def byte(self) -> int:
        """Read locations 0-7 as an MSB-first byte (location 0 is bit 7)."""
        return _byte_of(self.state[2])

    def step(self) -> None:
        """Execute one command (or the loop-or-halt check), advancing.

        The two effects live here rather than in the transition: this is
        the shell, so it is where an effect belongs.  A ``2`` only reads or
        writes at the two special pointer positions, so the position is
        tested here as well -- a ``2`` anywhere else must not touch I/O.
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
        self.state = _advance(self.state, self.code, byte)


def run(code: str, io: IO) -> None:
    """Run a 123 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
