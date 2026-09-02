"""Interpreter for Minifuck.

A binary tape where [ skips the next instruction when the flipped bit is 0
and . prints the first eight cells as a binary byte (reading a byte of input
instead when the pool is zero).  < moves the pointer left.

The program is not implicitly looped: execution halts when the instruction
pointer reaches the end of the code (the wiki talk page leaves the question
open; this interpreter does not assume an implicit loop).

Exhausted input raises :class:`EOFError` (the repo-wide convention).

Minifuck is the smallest interpreter in the repo, which makes it the one
worth writing as a *functional core with an imperative shell*: :class:`_State`
is an immutable snapshot of the machine, :func:`_advance` is a pure function
from one state to the next, and :class:`_Machine` is the thin mutable shell
the VM and the hang detector need (their protocol wants an in-place
``step()``, so the shell rebinds ``self.state`` rather than the core mutating
anything).

The one effect in the language is ``.``, whose behaviour depends on the tape:
a non-zero print window prints, a zero one reads.  A pure step cannot decide
that *and* perform it, so :func:`_advance` returns the next state paired with an
:class:`_Effect` describing what the shell owes the outside world.  Input
comes back the same way: :func:`_load` is the pure half of a read, splicing a
byte the shell has already fetched into the print window.  Nothing in the
core touches :class:`IO`.
"""

import sys
from typing import NamedTuple

from esolangs.interpreters.io import IO

#: Width of the print window: ``.`` reads cells 0-7 as one binary byte.
_WIDTH = 8

#: Mask of the print window, cells 0-7.
_WINDOW = (1 << _WIDTH) - 1


class _State(NamedTuple):
    """An immutable Minifuck machine state.

    The tape is an ``int`` used as a bitvector, cell *i* at bit *i*: the tape
    is binary, so a flip is ``tape ^ (1 << ptr)`` and no cell has to be
    copied to change one.  A tuple would be immutable too, but every flip
    would rebuild it, which makes a step cost O(tape) and a run quadratic --
    measured at 152x the mutable-list version by tape 20000.  An int is
    immutable *and* O(1) here, so a state can be shared, hashed, and compared
    without a defensive copy, which is what lets :meth:`_Machine.snapshot`
    hand its state straight to the cycle detector.

    ``length`` is carried because the int cannot report it: a tape of
    trailing zeros is the same int as a shorter one, and the growth rule
    below (and the list ``_Machine.tape`` hands back) both depend on where
    the tape actually ends.
    """

    code: str
    tape: int
    length: int
    ptr: int
    ind: int

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    @property
    def cells(self) -> list[int]:
        """The tape as a list of bits, the shape callers and tests expect."""
        return [(self.tape >> i) & 1 for i in range(self.length)]


class _Effect(NamedTuple):
    """What a pure step owes the outside world: at most one IO action.

    ``char`` is the byte ``.`` printed, or ``None``; ``reads`` is true when
    ``.`` found a zero print window and the shell must fetch a byte and pass
    it back through :func:`_load`.  Both are falsy for every other command,
    so the shell's fast path is a single truth test.
    """

    char: str | None = None
    reads: bool = False


#: The effect of a step that does no IO, shared rather than rebuilt per step.
_QUIET = _Effect()


def _start(code: str) -> _State:
    """Return the initial state: an eight-cell tape at the origin."""
    return _State(code, 0, _WIDTH, 0, 0)


def _pool(tape: int) -> int:
    """Read cells 0-7 as one binary byte, cell 0 the most significant bit.

    The tape numbers cells rightward from the origin but the byte is written
    most significant bit first, so the window is reversed on the way out --
    and on the way back in through :func:`_load`.  This is the only place the
    two orders meet; getting it backwards is invisible to the type checker.
    """
    window = tape & _WINDOW
    return sum(
        ((window >> i) & 1) << (_WIDTH - 1 - i)  #
        for i in range(_WIDTH)
    )


def _load(state: _State, byte: int) -> _State:
    """Splice ``byte`` into the print window, keeping the tape past it.

    Only the window's bits are replaced, so the boundary is exactly the
    window: clearing any further would silently drop cell 8 once the pointer
    had walked out that far.

    The ``& ~_WINDOW`` is defensive rather than load-bearing, and mutation
    testing reports it as a survivor for that reason: :func:`_advance` calls
    this only when it found a zero print window, so the bits being cleared
    are already zero (6016 calls checked, never once non-zero).  It stays
    because ``_load``'s contract is "replace the window", not "assume the
    caller zeroed it" -- but a mutant dropping the ``~`` is equivalent, not
    a test gap.
    """
    bits = sum(((byte >> (_WIDTH - 1 - i)) & 1) << i for i in range(_WIDTH))
    return state._replace(tape=(state.tape & ~_WINDOW) | bits)


def _advance(state: _State) -> tuple[_State, _Effect]:
    """Execute one instruction, returning the next state and its effect.

    Pure: the caller owns every side effect.  Stepping a halted state is a
    no-op that leaves the cursor where it is, matching the shell's contract.
    """
    if state.halted:
        return state, _QUIET

    ins = state.code[state.ind]
    tape, length, ptr, ind = state.tape, state.length, state.ptr, state.ind

    if ins == "<" and ptr:
        return state._replace(ptr=ptr - 1, ind=ind + 1), _QUIET
    if ins not in ".[":
        # Anything else is a comment character: only the cursor moves.
        return state._replace(ind=ind + 1), _QUIET

    # Both commands walk right and flip the cell they land on, growing the
    # tape so the cell *after* the pointer always exists for the skip below.
    # The appended cell is a zero, which the int already spells: only the
    # recorded length has to move.
    ptr += 1
    if ptr + 1 >= length:
        length += 1
    tape ^= 1 << ptr

    if ins == ".":
        # A non-zero window prints; a zero one reads, and the shell owes the
        # byte back through _load -- the decision is pure, the fetch is not.
        pool = _pool(tape)
        effect = _Effect(char=chr(pool)) if pool else _Effect(reads=True)
        return _State(state.code, tape, length, ptr, ind + 1), effect

    if not (tape >> ptr) & 1:
        # [ flipped the cell to 0: flip the one beyond it and skip ahead by
        # one instruction, on top of the advance every step makes.
        tape ^= 1 << (ptr + 1)
        ind += 1

    return _State(state.code, tape, length, ptr, ind + 1), _QUIET


class _Machine:
    """Per-run Minifuck state: the tape, pointer, and code cursor.

    The mutable shell around the pure core: ``step()`` executes one
    instruction and rebinds ``state``, performing whatever IO the core asked
    for; ``halted`` is true once the cursor reaches the end of the code.  The
    VM and the state-cycle hang detector expose this object (the tape never
    rewinds, so a Minifuck program always halts), and read ``tape``/``ptr``/
    ``ind`` off it, which the properties below forward to the state.
    """

    __slots__ = ("io", "state")

    def __init__(self, code: str, io: IO) -> None:
        """Start with an eight-cell tape at the origin."""
        self.io = io
        self.state = _start(code)

    @property
    def tape(self) -> list[int]:
        """The tape as a list, the shape callers and tests expect."""
        return self.state.cells

    @property
    def ptr(self) -> int:
        return self.state.ptr

    @property
    def ind(self) -> int:
        return self.state.ind

    # The VM's language-shaped view.  Minifuck is a binary tape walked by a
    # cursor: ``ip`` is that cursor, ``memory`` the cells, and there is no
    # stack.  These live here rather than in ``esolangs.vm`` so the mapping
    # sits with the machine that knows it; the lists are fresh copies, so a
    # caller cannot reach back into the tape through them.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state.ind

    @property
    def memory(self) -> list[int]:
        """The tape's cells."""
        return self.state.cells

    @property
    def stack(self) -> list[object]:
        """Minifuck has no stack."""
        return []

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state.halted

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        ``length`` rides along with the tape int: two tapes differing only in
        trailing zeros are the same int, so dropping it would call two
        distinct states a cycle.
        """
        state = self.state
        return (state.tape, state.length, state.ptr, state.ind, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the cursor."""
        state, effect = _advance(self.state)
        if effect.char is not None:
            self.io.print_char(effect.char)
        elif effect.reads:
            state = _load(state, self.io.input_char())
        self.state = state


def run(code: str, io: IO) -> None:
    """Run a Minifuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
