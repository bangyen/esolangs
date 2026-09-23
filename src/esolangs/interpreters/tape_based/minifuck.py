"""Interpreter for Minifuck.

A binary tape: ``[`` flips the current bit and skips the next instruction
when it became 0, ``.`` prints cells 0-7 as a byte or *reads* one when
they are zero, ``<`` moves left.  Not implicitly looped (the talk page
leaves it open): the run halts at the end of the code.  Exhausted input
raises :class:`EOFError`.  :func:`_advance` is a pure function from
:class:`_State` to the next state plus an :class:`_Effect` naming what
the shell owes; :func:`_load` is the pure half of a read.
"""

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: Width of the print window: ``.`` reads cells 0-7 as one binary byte.
_WIDTH = 8

#: Mask of the print window, cells 0-7.
_WINDOW = (1 << _WIDTH) - 1

#: ``(code, tape, length, ptr, ind)``: an immutable value, rebound per step.
#: The tape is an ``int`` bitvector, cell *i* at bit *i*: a flip is
#: ``tape ^ (1 << ptr)``, O(1) and immutable (a tuple rebuilt per flip was
#: 152x slower by tape 20000).  ``length`` is carried because trailing zeros
#: are invisible in the int.  A plain tuple: ``NamedTuple`` construction is
#: Python-level and this is built once per step (plain measured ~1.15x faster
#: end-to-end on a 300k-step run).
type _State = tuple[str, int, int, int, int]

#: What a pure step owes the outside world: ``(char, reads)``, ``char`` the
#: byte printed or ``None``, ``reads`` meaning the shell must fetch a byte
#: for :func:`_load`.
type _Effect = tuple[str | None, bool]

#: The effect of a step that does no IO, shared rather than rebuilt per step.
_QUIET: _Effect = (None, False)


def _start(code: str) -> _State:
    """Return the initial state: an eight-cell tape at the origin."""
    return (code, 0, _WIDTH, 0, 0)


def _pool(tape: int) -> int:
    """Read cells 0-7 as one binary byte, cell 0 the most significant bit.

    The one place the tape's and the byte's orders meet.
    """
    window = tape & _WINDOW
    return sum(
        ((window >> i) & 1) << (_WIDTH - 1 - i)  #
        for i in range(_WIDTH)
    )


def _load(state: _State, byte: int) -> _State:
    """Splice ``byte`` into the print window, keeping the tape past it.

    The ``& ~_WINDOW`` is defensive (the window is already zero when this is
    called, 6016 calls checked); a mutant dropping it is equivalent, not a gap.
    """
    code, tape, length, ptr, ind = state
    bits = sum(((byte >> (_WIDTH - 1 - i)) & 1) << i for i in range(_WIDTH))
    return (code, (tape & ~_WINDOW) | bits, length, ptr, ind)


def _step(
    ins: str, tape: int, length: int, ptr: int
) -> tuple[int, int, int, bool, str | None, bool]:
    """One instruction as plain scalars: the language, with no state objects.

    Returns ``(tape, length, ptr, skipped, char, reads)``.  The single
    definition: :func:`_advance` wraps it, and the boolean generator's
    emitter calls it directly (a state object per step measured 4.2x).
    """
    if ins == "<":
        return (tape, length, ptr - 1 if ptr else ptr, False, None, False)
    if ins not in ".[":
        # Anything else is a comment character: only the cursor moves.
        return (tape, length, ptr, False, None, False)

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
        if pool:
            return (tape, length, ptr, False, chr(pool), False)
        return (tape, length, ptr, False, None, True)

    if not (tape >> ptr) & 1:
        # [ flipped the cell to 0: flip the one beyond it and skip ahead by
        # one instruction, on top of the advance every step makes.
        tape ^= 1 << (ptr + 1)
        return (tape, length, ptr, True, None, False)

    return (tape, length, ptr, False, None, False)


def _advance(state: _State) -> tuple[_State, _Effect]:
    """Execute one instruction, returning the next state and its effect.

    Pure; stepping a halted state is a no-op.
    """
    code, tape, length, ptr, ind = state
    if ind >= len(code):
        return state, _QUIET

    ins = code[ind]
    tape, length, ptr, skipped, char, reads = _step(ins, tape, length, ptr)

    # A collapsed ``[`` skips the next instruction, on top of the advance
    # every step makes.
    ind = ind + (2 if skipped else 1)

    if char is not None:
        return (code, tape, length, ptr, ind), (char, False)
    if reads:
        return (code, tape, length, ptr, ind), (None, True)
    return (code, tape, length, ptr, ind), _QUIET


class _Machine:
    """Per-run Minifuck state: the tape, pointer, and code cursor.

    The tape never rewinds, so a program always halts.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with an eight-cell tape at the origin."""
        self.io = io
        self.state = _start(code)

    @property
    def tape(self) -> list[int]:
        """The tape as a list, the shape callers and tests expect."""
        _, tape, length, _, _ = self.state
        return [(tape >> i) & 1 for i in range(length)]

    @property
    def ptr(self) -> int:
        return self.state[3]

    @property
    def ind(self) -> int:
        return self.state[4]

    # The VM's language-shaped view.  Minifuck is a binary tape walked by a
    # cursor: ``ip`` is that cursor, ``memory`` the cells, and there is no
    # stack.  These live here rather than in ``esolangs.vm`` so the mapping
    # sits with the machine that knows it; the lists are fresh copies, so a
    # caller cannot reach back into the tape through them.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state[4]

    @property
    def memory(self) -> list[int]:
        """The tape's cells."""
        return self.tape

    @property
    def stack(self) -> list[object]:
        """Minifuck has no stack."""
        return []

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[4] >= len(self.state[0])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        ``length`` rides along, since trailing zeros are invisible in the int.
        """
        _, tape, length, ptr, ind = self.state
        return (tape, length, ptr, ind, self.io.position())

    def step(self) -> None:
        """Execute one instruction, advancing the cursor."""
        state, effect = _advance(self.state)
        if effect[0] is not None:
            self.io.print_char(effect[0])
        elif effect[1]:
            state = _load(state, self.io.input_char())
        self.state = state


def run(code: str, io: IO) -> None:
    """Run a Minifuck program."""
    tape = 0
    length = _WIDTH
    ptr = 0
    ind = 0
    while ind < len(code):
        tape, length, ptr, skipped, char, reads = _step(code[ind], tape, length, ptr)
        ind += 2 if skipped else 1
        if char is not None:
            io.print_char(char)
        elif reads:
            _, tape, _, _, _ = _load((code, tape, length, ptr, ind), io.input_char())


if __name__ == "__main__":
    script_main(run)
